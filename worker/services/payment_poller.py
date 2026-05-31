import logging

from sqlalchemy import select

from bot.services.crypto_pay import CryptoPayClient
from bot.services.subscriptions import mark_payment_paid
from db.models import Payment, PaymentStatus
from db.session import SessionLocal

logger = logging.getLogger(__name__)


async def poll_pending_payments() -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Payment).where(Payment.status == PaymentStatus.PENDING)
        )
        pending = result.scalars().all()
        if not pending:
            return

        client = CryptoPayClient()
        if not client._token:
            return

        ids = [p.invoice_id for p in pending]
        try:
            invoices = await client.get_invoices(ids)
        except Exception as exc:
            logger.warning("Crypto Pay poll failed: %s", exc)
            return

        by_id = {str(i.get("invoice_id")): i for i in invoices}
        for payment in pending:
            inv = by_id.get(payment.invoice_id)
            if not inv:
                continue
            if inv.get("status") == "paid":
                await mark_payment_paid(session, payment)
                logger.info("Payment %s activated for user %s", payment.invoice_id, payment.user_id)
            elif inv.get("status") == "expired":
                payment.status = PaymentStatus.EXPIRED

        await session.commit()
