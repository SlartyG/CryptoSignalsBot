from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.users import get_active_subscription
from db.models import Payment, PaymentStatus, Subscription, SubscriptionStatus

PLAN_DAYS = {"1m": 30, "3m": 90, "12m": 365}


async def expire_user_pending_payments(
    session: AsyncSession,
    user_id: int,
    *,
    except_invoice_id: str | None = None,
) -> int:
    """Mark other pending payments for user as expired (new invoice replaces them)."""
    q = (
        update(Payment)
        .where(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.PENDING,
        )
        .values(status=PaymentStatus.EXPIRED)
    )
    if except_invoice_id:
        q = q.where(Payment.invoice_id != except_invoice_id)
    result = await session.execute(q)
    return result.rowcount or 0


async def activate_subscription(
    session: AsyncSession,
    user_id: int,
    plan: str,
    source: str = "payment",
) -> Subscription:
    now = datetime.now(timezone.utc)
    days = PLAN_DAYS.get(plan, 30)
    delta = timedelta(days=days)

    active = await get_active_subscription(session, user_id)
    if active:
        base = active.ends_at if active.ends_at > now else now
        active.ends_at = base + delta
        active.plan = plan
        await session.flush()
        return active

    sub = Subscription(
        user_id=user_id,
        plan=plan,
        starts_at=now,
        ends_at=now + delta,
        source=source,
        status=SubscriptionStatus.ACTIVE,
    )
    session.add(sub)
    await session.flush()
    return sub


async def mark_payment_paid(session: AsyncSession, payment: Payment) -> Subscription | None:
    from bot.services.analytics import track

    if payment.status == PaymentStatus.PAID:
        return await get_active_subscription(session, payment.user_id)

    payment.status = PaymentStatus.PAID
    payment.paid_at = datetime.now(timezone.utc)
    sub = await activate_subscription(session, payment.user_id, payment.plan)
    await track(
        session,
        payment.user_id,
        "payment_paid",
        plan=payment.plan,
        amount_usdt=payment.amount_usdt,
        provider=payment.provider,
    )
    return sub
