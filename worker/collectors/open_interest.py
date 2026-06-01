import logging

from sqlalchemy.ext.asyncio import AsyncSession

from engine.rules import check_oi_price
from engine.signal_engine import emit_signal, record_metric
from shared.collect_batch import run_batched
from shared.universe import get_active_symbols
from worker.bybit.client import BybitClient

logger = logging.getLogger(__name__)


async def run_oi_collector(session: AsyncSession, client: BybitClient) -> None:
    symbols = await get_active_symbols(session)

    async def _process(symbol: str) -> None:
        try:
            oi_list, latency = await client.get_open_interest(symbol)
            klines, _ = await client.get_klines(symbol, interval="60", limit=3)
            if len(klines) < 2:
                return
            last_close = float(klines[0][4])
            prev_close = float(klines[1][4])
            price_change = (last_close - prev_close) / prev_close * 100 if prev_close else 0
            candidate = check_oi_price(symbol, oi_list, price_change)
            if candidate:
                await emit_signal(session, candidate)
            await record_metric(session, "open_interest", True, latency)
        except Exception as exc:
            logger.exception("OI collector error %s", symbol)
            await record_metric(session, "open_interest", False, error=str(exc))

    await run_batched(symbols, _process)
    await session.commit()
