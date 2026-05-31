from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserSignalSetting
from shared.signal_types import SignalType

ALL_SIGNAL_TYPES = [t.value for t in SignalType]


async def ensure_default_settings(session: AsyncSession, user_id: int) -> None:
    for st in ALL_SIGNAL_TYPES:
        result = await session.execute(
            select(UserSignalSetting).where(
                UserSignalSetting.user_id == user_id,
                UserSignalSetting.signal_type == st,
            )
        )
        if result.scalar_one_or_none() is None:
            session.add(UserSignalSetting(user_id=user_id, signal_type=st, enabled=True))


async def toggle_signal_type(
    session: AsyncSession, user_id: int, signal_type: str
) -> bool:
    result = await session.execute(
        select(UserSignalSetting).where(
            UserSignalSetting.user_id == user_id,
            UserSignalSetting.signal_type == signal_type,
        )
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        session.add(UserSignalSetting(user_id=user_id, signal_type=signal_type, enabled=False))
        return False
    setting.enabled = not setting.enabled
    return setting.enabled


async def get_settings_map(session: AsyncSession, user_id: int) -> dict[str, bool]:
    await ensure_default_settings(session, user_id)
    result = await session.execute(
        select(UserSignalSetting).where(UserSignalSetting.user_id == user_id)
    )
    return {s.signal_type: s.enabled for s in result.scalars().all() if s.signal_type in ALL_SIGNAL_TYPES}


async def toggle_symbol(
    session: AsyncSession, user_id: int, symbol: str, universe: list[str]
) -> list[str]:
    result = await session.execute(
        select(UserSignalSetting).where(
            UserSignalSetting.user_id == user_id,
            UserSignalSetting.signal_type == "symbols",
        )
    )
    setting = result.scalar_one_or_none()
    if setting is None or not setting.symbols:
        current = list(universe)
    else:
        current = list(setting.symbols)

    if symbol in current:
        current.remove(symbol)
    else:
        current.append(symbol)

    if setting is None:
        session.add(
            UserSignalSetting(user_id=user_id, signal_type="symbols", enabled=True, symbols=current)
        )
    else:
        setting.symbols = current
    return current
