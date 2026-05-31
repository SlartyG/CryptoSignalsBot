import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from db.models import DeliveryLog
from db.session import SessionLocal
from shared.config import settings
from worker.notifier.queue import pop_next

logger = logging.getLogger(__name__)


async def run_notifier(stop_event: asyncio.Event) -> None:
    if not settings.bot_token:
        logger.error("BOT_TOKEN not set, notifier disabled")
        return

    bot = Bot(token=settings.bot_token)
    try:
        while not stop_event.is_set():
            item = await pop_next()
            if not item:
                await asyncio.sleep(0.5)
                continue

            telegram_id = item["telegram_id"]
            text = item["text"]
            signal_id = item["signal_id"]
            user_id = item["user_id"]
            priority = item.get("priority", 2)

            error = None
            try:
                await bot.send_message(telegram_id, text, disable_web_page_preview=True)
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after + 1)
                continue
            except TelegramForbiddenError:
                error = "bot_blocked"
            except Exception as exc:
                error = str(exc)
                logger.warning("Send failed %s: %s", telegram_id, exc)

            async with SessionLocal() as session:
                session.add(
                    DeliveryLog(
                        signal_id=signal_id,
                        user_id=user_id,
                        priority=priority,
                        sent_at=datetime.now(timezone.utc) if not error else None,
                        error=error,
                    )
                )
                await session.commit()

            await asyncio.sleep(0.04)
    finally:
        await bot.session.close()
