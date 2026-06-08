from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketUniverse
from shared.signal_types import ALWAYS_SYMBOLS, DEFAULT_SYMBOLS_COUNT, UNIVERSE_SIZE


async def get_active_symbols(session: AsyncSession) -> list[str]:
    entries = await get_universe_entries(session)
    if entries:
        return [e[0] for e in entries]
    return list(ALWAYS_SYMBOLS)


def _dedupe_universe_rows(
    rows: list[tuple[str, int, float]],
) -> list[tuple[str, int, float]]:
    """One row per symbol; keep the best (lowest) rank if duplicates exist."""
    best: dict[str, tuple[str, int, float]] = {}
    for sym, rank, turnover in rows:
        entry = (sym, rank, float(turnover or 0))
        if sym not in best or rank < best[sym][1]:
            best[sym] = entry
    return sorted(best.values(), key=lambda item: item[1])


async def get_universe_entries(session: AsyncSession) -> list[tuple[str, int, float]]:
    """symbol, rank, turnover_24h (0 if missing)."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(MarketUniverse.symbol, MarketUniverse.rank, MarketUniverse.turnover_24h)
        .where(MarketUniverse.active_to.is_(None))
        .order_by(MarketUniverse.rank)
    )
    rows = result.all()
    if not rows:
        return []
    parsed = [(sym, rank, float(turnover or 0)) for sym, rank, turnover in rows]
    return _dedupe_universe_rows(parsed)


async def get_base_symbols(session: AsyncSession) -> list[str]:
    symbols = await get_active_symbols(session)
    return symbols[:DEFAULT_SYMBOLS_COUNT]


async def get_default_paid_symbols(session: AsyncSession) -> list[str]:
    return await get_base_symbols(session)


def sort_symbols(
    symbols: list[str],
    sort_mode: str,
    rank_map: dict[str, int],
) -> list[str]:
    if sort_mode == "alpha":
        return sorted(symbols)
    return sorted(symbols, key=lambda s: rank_map.get(s, UNIVERSE_SIZE + 1))
