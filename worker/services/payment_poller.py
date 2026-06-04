import logging

from sqlalchemy import select

from bot.services.crypto_pay import CryptoPayClient
from bot.services.payment_verify import verify_paid_invoice
from bot.services.subscriptions import mark_payment_paid
from bot.services.xrocket_pay import XRocketPayClient
from db.models import Payment, PaymentProvider, PaymentStatus, Subscription
from db.session import SessionLocal
from worker.services.payment_notify import notify_payment_success

logger = logging.getLogger(__name__)


async def _poll_cryptopay(session, pending: list[Payment]) -> list[tuple[Payment, Subscription]]:
    payments = [p for p in pending if p.provider == PaymentProvider.CRYPTO_PAY]
    if not payments:
        return []

    client = CryptoPayClient()
    if not client._token:
        return []

    ids = [p.invoice_id for p in payments]
    try:
        invoices = await client.get_invoices(ids)
    except Exception as exc:
        logger.warning("Crypto Pay poll failed: %s", exc)
        return []

    by_id = {str(i.get("invoice_id")): i for i in invoices}
    activated: list[tuple[Payment, Subscription]] = []
    for payment in payments:
        inv = by_id.get(payment.invoice_id)
        if not inv:
            continue
        if inv.get("status") == "expired":
            payment.status = PaymentStatus.EXPIRED
            continue
        if inv.get("status") != "paid":
            continue
        err = verify_paid_invoice(payment, inv)
        if err:
            logger.warning(
                "Crypto Pay invoice %s verification failed: %s",
                payment.invoice_id,
                err,
            )
            continue
        sub = await mark_payment_paid(session, payment)
        if sub:
            activated.append((payment, sub))
            logger.info(
                "Payment %s (cryptopay) activated for user %s",
                payment.invoice_id,
                payment.user_id,
            )
    return activated


async def _poll_xrocket(session, pending: list[Payment]) -> list[tuple[Payment, Subscription]]:
    payments = [p for p in pending if p.provider == PaymentProvider.XROCKET]
    if not payments:
        return []

    client = XRocketPayClient()
    if not client._token:
        return []

    activated: list[tuple[Payment, Subscription]] = []
    for payment in payments:
        try:
            inv = await client.get_invoice(payment.invoice_id)
        except Exception as exc:
            logger.warning("xRocket poll failed for %s: %s", payment.invoice_id, exc)
            continue
        if not inv:
            continue
        status = inv.get("status")
        if status == "expired":
            payment.status = PaymentStatus.EXPIRED
            continue
        if status != "paid":
            continue
        err = verify_paid_invoice(payment, inv)
        if err:
            logger.warning(
                "xRocket invoice %s verification failed: %s",
                payment.invoice_id,
                err,
            )
            continue
        sub = await mark_payment_paid(session, payment)
        if sub:
            activated.append((payment, sub))
            logger.info(
                "Payment %s (xrocket) activated for user %s",
                payment.invoice_id,
                payment.user_id,
            )
    return activated


async def poll_pending_payments() -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Payment).where(Payment.status == PaymentStatus.PENDING)
        )
        pending = result.scalars().all()
        if not pending:
            return

        activated = await _poll_cryptopay(session, pending)
        activated += await _poll_xrocket(session, pending)
        await session.commit()

    for _payment, sub in activated:
        await notify_payment_success(sub.user_id, sub.ends_at)
