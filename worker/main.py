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
            await asyncio.wait_for(stop_event.wait(), timeout=30)
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


async def _supervised(name: str, coro_fn, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await coro_fn(stop_event)
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker task %s crashed, retry in 10s", name)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=10)
                return
            except asyncio.TimeoutError:
                pass


async def main() -> None:
    stop_event = asyncio.Event()
    tasks = [
        asyncio.create_task(_supervised("funding", lambda e: periodic(e, 300, "funding", run_funding_collector), stop_event)),
        asyncio.create_task(_supervised("oi", lambda e: periodic(e, 300, "oi", run_oi_collector), stop_event)),
        asyncio.create_task(_supervised("volume", lambda e: periodic(e, 900, "volume", run_volume_collector), stop_event)),
        asyncio.create_task(_supervised("universe", universe_scheduler, stop_event)),
        asyncio.create_task(_supervised("liquidations", liquidation_listener, stop_event)),
        asyncio.create_task(_supervised("notifier", run_notifier, stop_event)),
        asyncio.create_task(_supervised("payments", payment_poller, stop_event)),
        asyncio.create_task(_supervised("reminders", reminder_scheduler, stop_event)),
    ]

    try:
        async with SessionLocal() as session:
            client = BybitClient()
            await client.start()
            try:
                await refresh_universe(session, client)
            finally:
                await client.close()
    except Exception:
        logger.exception("Initial universe refresh failed, worker continues")

    logger.info("Worker started")
    try:
        await asyncio.gather(*tasks)
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        await close_redis()


if __name__ == "__main__":
    asyncio.run(main())
