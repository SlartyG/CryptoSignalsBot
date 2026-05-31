import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AdminAudit,
    CollectorMetric,
    Payment,
    PaymentStatus,
    SignalLog,
    Subscription,
    SubscriptionStatus,
    User,
)
from shared.config import is_admin, settings

logger = logging.getLogger(__name__)
router = Router()


async def _audit(session: AsyncSession, admin_id: int, action: str, payload: dict | None = None) -> None:
    session.add(AdminAudit(admin_id=admin_id, action=action, payload_json=payload))


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Admin commands:\n"
        "/grant <telegram_id> <days>\n"
        "/revoke <telegram_id>\n"
        "/ban <telegram_id>\n"
        "/unban <telegram_id>\n"
        "/broadcast <free|paid|all> <text>\n"
        "/logs_signals [N]\n"
        "/logs_collectors [N]\n"
        "/stats"
    )


@router.message(Command("grant"))
async def cmd_grant(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /grant <telegram_id> <days>")
        return
    tg_id = int(parts[1])
    days = int(parts[2])
    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("User not found")
        return
    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user.id,
        plan="1m",
        starts_at=now,
        ends_at=now + timedelta(days=days),
        source="admin_grant",
        status=SubscriptionStatus.ACTIVE,
    )
    session.add(sub)
    await _audit(session, message.from_user.id, "grant", {"user_id": user.id, "days": days})
    await session.commit()
    await message.answer(f"Granted {days} days to {tg_id}")


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /revoke <telegram_id>")
        return
    tg_id = int(parts[1])
    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("User not found")
        return
    subs = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
    )
    for sub in subs.scalars():
        sub.status = SubscriptionStatus.REVOKED
    await _audit(session, message.from_user.id, "revoke", {"user_id": user.id})
    await session.commit()
    await message.answer(f"Revoked paid for {tg_id}")


@router.message(Command("ban"))
async def cmd_ban(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    tg_id = int(message.text.split()[1])
    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if user:
        user.banned = True
        await _audit(session, message.from_user.id, "ban", {"user_id": user.id})
        await session.commit()
    await message.answer(f"Banned {tg_id}")


@router.message(Command("unban"))
async def cmd_unban(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    tg_id = int(message.text.split()[1])
    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if user:
        user.banned = False
        await _audit(session, message.from_user.id, "unban", {"user_id": user.id})
        await session.commit()
    await message.answer(f"Unbanned {tg_id}")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /broadcast <free|paid|all> <text>")
        return
    target, text = parts[1], parts[2]
    result = await session.execute(
        select(User).where(User.banned.is_(False), User.consented_at.is_not(None))
    )
    users = result.scalars().all()
    bot = Bot(token=settings.bot_token)
    sent = 0
    try:
        for user in users:
            from bot.services.users import get_active_subscription

            sub = await get_active_subscription(session, user.id)
            is_paid = sub is not None
            if target == "free" and is_paid:
                continue
            if target == "paid" and not is_paid:
                continue
            try:
                await bot.send_message(user.telegram_id, text)
                sent += 1
            except Exception:
                pass
    finally:
        await bot.session.close()
    await _audit(session, message.from_user.id, "broadcast", {"target": target, "sent": sent})
    await session.commit()
    await message.answer(f"Broadcast sent to {sent} users")


@router.message(Command("logs_signals"))
async def cmd_logs_signals(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    n = int(message.text.split()[1]) if len(message.text.split()) > 1 else 10
    result = await session.execute(
        select(SignalLog).order_by(SignalLog.created_at.desc()).limit(n)
    )
    lines = []
    for s in result.scalars():
        lines.append(f"{s.created_at:%m-%d %H:%M} {s.symbol} {s.type} {s.confidence}")
    await message.answer("\n".join(lines) or "No signals")


@router.message(Command("logs_collectors"))
async def cmd_logs_collectors(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    n = int(message.text.split()[1]) if len(message.text.split()) > 1 else 10
    result = await session.execute(
        select(CollectorMetric).order_by(CollectorMetric.ts.desc()).limit(n)
    )
    lines = []
    for m in result.scalars():
        status = "OK" if m.success else f"ERR {m.error}"
        lines.append(f"{m.ts:%m-%d %H:%M} {m.collector_name} {status}")
    await message.answer("\n".join(lines) or "No metrics")


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    total = await session.scalar(select(func.count(User.id)))
    banned = await session.scalar(select(func.count(User.id)).where(User.banned.is_(True)))
    now = datetime.now(timezone.utc)
    active_subs = await session.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.ends_at > now,
        )
    )
    mrr = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount_usdt), 0)).where(
            Payment.status == PaymentStatus.PAID,
            Payment.paid_at >= now - timedelta(days=30),
        )
    )
    await message.answer(
        f"Users: {total}\nBanned: {banned}\nActive subs: {active_subs}\nMRR~USDT: {mrr or 0:.2f}"
    )
