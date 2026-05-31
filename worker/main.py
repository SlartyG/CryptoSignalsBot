import asyncio
import logging
import sys
from datetime import datetime, timezone

from db.session import SessionLocal
from shared.redis_client import close_redis
from worker.bybit.client import BybitClient
from worker.collectors.funding import run_funding_collector
from worker.collectors.liquidations import liquidation_listener
from worker.collectors.open_interest import run_oi_collector
from worker.collectors.volume import run_volume_collector
from worker.jobs.subscription_reminders import run_subscription_reminders
from worker.jobs.universe import refresh_universe
from worker.notifier.worker import run_notifier
from worker.services.payment_poller import poll_pending_payments

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def periodic(
    stop_event: asyncio.Event,
    interval_sec: int,
    name: str,
    coro_factory,
) -> None:
    while not stop_event.is_set():
        try:
            async with SessionLocal() as session:
                client = BybitClient()
                await client.start()
                try:
                    await coro_factory(session, client)
                finally:
                    await client.close()
        except Exception:
            logger.exception("%s cycle failed", name)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_sec)
            break
        except asyncio.TimeoutError:
            pass


async def universe_scheduler(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with SessionLocal() as session:
                client = BybitClient()
                await client.start()
                try:
                    await refresh_universe(session, client)
                finally:
                    await client.close()
        except Exception:
            logger.exception("Universe refresh failed")

        now = datetime.now(timezone.utc)
        next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.hour >= 0:
            from datetime import timedelta

            next_midnight = next_midnight + timedelta(days=1)
        wait_sec = max(3600, (next_midnight - now).total_seconds())
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=min(wait_sec, 86400))
            break
        except asyncio.TimeoutError:
            pass


async def payment_poller(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await poll_pending_payments()
        except Exception:
            logger.exception("Payment poller failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=120)
            break
        except asyncio.TimeoutError:
            pass


async def reminder_scheduler(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await run_subscription_reminders()
        except Exception:
            logger.exception("Reminder job failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600)
            break
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    stop_event = asyncio.Event()
    tasks = [
        asyncio.create_task(periodic(stop_event, 300, "funding", run_funding_collector)),
        asyncio.create_task(periodic(stop_event, 300, "oi", run_oi_collector)),
        asyncio.create_task(periodic(stop_event, 900, "volume", run_volume_collector)),
        asyncio.create_task(universe_scheduler(stop_event)),
        asyncio.create_task(liquidation_listener(stop_event)),
        asyncio.create_task(run_notifier(stop_event)),
        asyncio.create_task(payment_poller(stop_event)),
        asyncio.create_task(reminder_scheduler(stop_event)),
    ]

    async with SessionLocal() as session:
        client = BybitClient()
        await client.start()
        try:
            await refresh_universe(session, client)
        finally:
            await client.close()

    logger.info("Worker started")
    try:
        await asyncio.gather(*tasks)
    finally:
        stop_event.set()
        await close_redis()


if __name__ == "__main__":
    asyncio.run(main())
