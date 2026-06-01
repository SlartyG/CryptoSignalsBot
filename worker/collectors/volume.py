import logging

from sqlalchemy.ext.asyncio import AsyncSession

from engine.rules import check_volume
from engine.signal_engine import emit_signal, record_metric
from shared.collect_batch import run_batched
from shared.universe import get_active_symbols
from worker.bybit.client import BybitClient

logger = logging.getLogger(__name__)


async def run_volume_collector(session: AsyncSession, client: BybitClient) -> None:
    symbols = await get_active_symbols(session)

    async def _process(symbol: str) -> None:
        try:
            klines, latency = await client.get_klines(symbol, interval="60", limit=168)
            if not klines:
                return
            current_volume = float(klines[0][5])
            candidate = check_volume(symbol, klines, current_volume)
            if candidate:
                await emit_signal(session, candidate)
            await record_metric(session, "volume", True, latency)
        except Exception as exc:
            logger.exception("Volume collector error %s", symbol)
            await record_metric(session, "volume", False, error=str(exc))

    await run_batched(symbols, _process)
    await session.commit()
