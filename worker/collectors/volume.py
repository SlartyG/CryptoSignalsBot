import logging

from sqlalchemy.ext.asyncio import AsyncSession

from engine.rules import check_volume
from engine.signal_engine import emit_signal, record_metric
from worker.bybit.client import BybitClient
from shared.universe import get_active_symbols

logger = logging.getLogger(__name__)


async def run_volume_collector(session: AsyncSession, client: BybitClient) -> None:
    symbols = await get_active_symbols(session)
    for symbol in symbols:
        try:
            klines, latency = await client.get_klines(symbol, interval="60", limit=168)
            if not klines:
                continue
            current_volume = float(klines[0][5])
            candidate = check_volume(symbol, klines, current_volume)
            if candidate:
                await emit_signal(session, candidate)
            await record_metric(session, "volume", True, latency)
        except Exception as exc:
            logger.exception("Volume collector error %s", symbol)
            await record_metric(session, "volume", False, error=str(exc))
    await session.commit()
