import logging

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CollectorMetric, SignalLog
from engine.cooldown import is_on_cooldown, set_cooldown
from engine.models import SignalCandidate
from worker.notifier.dispatch import enqueue_signal_delivery

logger = logging.getLogger(__name__)


async def record_metric(
    session: AsyncSession,
    name: str,
    success: bool,
    latency_ms: int | None = None,
    error: str | None = None,
) -> None:
    session.add(
        CollectorMetric(
            collector_name=name,
            success=success,
            latency_ms=latency_ms,
            error=error,
        )
    )


async def emit_signal(session: AsyncSession, candidate: SignalCandidate) -> SignalLog | None:
    if await is_on_cooldown(candidate.cooldown_key):
        return None

    signal = SignalLog(
        type=candidate.type.value,
        symbol=candidate.symbol,
        payload_json={
            **candidate.payload,
            "bias": candidate.bias.value,
        },
        confidence=candidate.confidence.value,
    )
    session.add(signal)
    await session.flush()

    await set_cooldown(candidate.type.value, candidate.cooldown_key)
    logger.info(
        "Signal emitted: %s %s %s",
        candidate.type.value,
        candidate.symbol,
        candidate.confidence.value,
    )

    await enqueue_signal_delivery(session, signal.id)
    return signal
