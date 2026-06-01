from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Payment, PaymentStatus, Subscription, SubscriptionStatus


async def activate_subscription(
    session: AsyncSession,
    user_id: int,
    plan: str,
    source: str = "payment",
) -> Subscription:
    now = datetime.now(timezone.utc)
    days = {"1m": 30, "3m": 90, "12m": 365}.get(plan, 30)
    sub = Subscription(
        user_id=user_id,
        plan=plan,
        starts_at=now,
        ends_at=now + timedelta(days=days),
        source=source,
        status=SubscriptionStatus.ACTIVE,
    )
    session.add(sub)
    await session.flush()
    return sub


async def mark_payment_paid(session: AsyncSession, payment: Payment) -> Subscription:
    from bot.services.analytics import track

    payment.status = PaymentStatus.PAID
    payment.paid_at = datetime.now(timezone.utc)
    sub = await activate_subscription(session, payment.user_id, payment.plan)
    await track(
        session,
        payment.user_id,
        "payment_paid",
        plan=payment.plan,
        amount_usdt=payment.amount_usdt,
    )
    return sub
