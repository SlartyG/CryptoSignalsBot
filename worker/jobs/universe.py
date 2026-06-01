import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketUniverse
from shared.signal_types import ALWAYS_SYMBOLS, UNIVERSE_SIZE
from worker.bybit.client import BybitClient

logger = logging.getLogger(__name__)


async def get_active_symbols(session: AsyncSession) -> list[str]:
    from shared.universe import get_active_symbols as _get

    return await _get(session)


async def refresh_universe(session: AsyncSession, client: BybitClient) -> list[str]:
    tickers = await client.get_tickers_linear()
    usdt = [t for t in tickers if t.get("symbol", "").endswith("USDT")]
    usdt.sort(key=lambda t: float(t.get("turnover24h") or 0), reverse=True)

    top: list[str] = []
    turnover_map: dict[str, float] = {}
    seen: set[str] = set()
    for t in usdt:
        sym = t["symbol"]
        if sym in seen:
            continue
        seen.add(sym)
        top.append(sym)
        turnover_map[sym] = float(t.get("turnover24h") or 0)
        if len(top) >= UNIVERSE_SIZE:
            break

    for sym in ALWAYS_SYMBOLS:
        if sym not in top:
            top.insert(0, sym)
            if sym not in turnover_map:
                turnover_map[sym] = 0.0
    top = top[:UNIVERSE_SIZE]

    now = datetime.now(timezone.utc)
    await session.execute(
        update(MarketUniverse)
        .where(MarketUniverse.active_to.is_(None))
        .values(active_to=now)
    )
    for rank, symbol in enumerate(top, start=1):
        session.add(
            MarketUniverse(
                symbol=symbol,
                rank=rank,
                turnover_24h=turnover_map.get(symbol),
                active_from=now,
            )
        )

    await session.commit()
    logger.info("Universe refreshed: %d symbols", len(top))
    return top
