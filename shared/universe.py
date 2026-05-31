from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketUniverse
from shared.signal_types import ALWAYS_SYMBOLS


async def get_active_symbols(session: AsyncSession) -> list[str]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(MarketUniverse.symbol)
        .where(MarketUniverse.active_to.is_(None))
        .order_by(MarketUniverse.rank)
    )
    symbols = list(result.scalars().all())
    if symbols:
        return symbols
    return list(ALWAYS_SYMBOLS)
