import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.users import get_active_subscription
from db.models import SignalLog, User, UserSignalSetting
from shared.signal_types import FREE_DELAY_SEC
from shared.universe import get_active_symbols, get_base_symbols, get_default_paid_symbols
from worker.notifier.formatter import format_signal_message
from worker.notifier.queue import enqueue

PRIORITY_PAID = 1
PRIORITY_FREE = 2


async def _user_enabled(session: AsyncSession, user_id: int, signal_type: str) -> bool:
    result = await session.execute(
        select(UserSignalSetting).where(
            UserSignalSetting.user_id == user_id,
            UserSignalSetting.signal_type == signal_type,
        )
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        return True
    return setting.enabled


async def _user_symbols(session: AsyncSession, user_id: int, universe: list[str]) -> list[str]:
    result = await session.execute(
        select(UserSignalSetting).where(
            UserSignalSetting.user_id == user_id,
            UserSignalSetting.signal_type == "symbols",
        )
    )
    setting = result.scalar_one_or_none()
    if setting and setting.symbols:
        return [s for s in setting.symbols if s in universe]
    default = await get_default_paid_symbols(session)
    return [s for s in default if s in universe]


async def enqueue_signal_delivery(session: AsyncSession, signal_id: int) -> None:
    signal = await session.get(SignalLog, signal_id)
    if not signal:
        return

    universe = await get_active_symbols(session)
    base_symbols = await get_base_symbols(session)
    result = await session.execute(
        select(User).where(User.banned.is_(False), User.consented_at.is_not(None))
    )
    users = result.scalars().all()
    now = time.time()

    for user in users:
        if not await _user_enabled(session, user.id, signal.type):
            continue

        sub = await get_active_subscription(session, user.id)
        is_paid = sub is not None

        if is_paid:
            allowed = await _user_symbols(session, user.id, universe)
            if signal.symbol not in allowed:
                continue
            priority = PRIORITY_PAID
            deliver_at = now
        else:
            if signal.symbol not in base_symbols:
                continue
            priority = PRIORITY_FREE
            deliver_at = now + FREE_DELAY_SEC

        text = format_signal_message(user.language, signal)
        await enqueue(
            user.id,
            user.telegram_id,
            signal.id,
            priority,
            text,
            deliver_at=deliver_at,
        )
