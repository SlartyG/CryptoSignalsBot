import logging

from sqlalchemy.ext.asyncio import AsyncSession

from engine.rules import check_funding
from engine.signal_engine import emit_signal, record_metric
from worker.bybit.client import BybitClient
from shared.universe import get_active_symbols

logger = logging.getLogger(__name__)


async def run_funding_collector(session: AsyncSession, client: BybitClient) -> None:
    symbols = await get_active_symbols(session)
    for symbol in symbols:
        try:
            rates, latency = await client.get_funding_history(symbol)
            candidate = check_funding(symbol, rates)
            if candidate:
                await emit_signal(session, candidate)
            await record_metric(session, "funding", True, latency)
        except Exception as exc:
            logger.exception("Funding collector error %s", symbol)
            await record_metric(session, "funding", False, error=str(exc))
    await session.commit()
