import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import select

from db.models import Subscription, SubscriptionStatus, User
from db.session import SessionLocal
from shared.config import settings

logger = logging.getLogger(__name__)

REMINDER_DAYS = (7, 3, 1)


async def run_subscription_reminders() -> None:
    if not settings.bot_token:
        return

    bot = Bot(token=settings.bot_token)
    now = datetime.now(timezone.utc)

    try:
        async with SessionLocal() as session:
            result = await session.execute(
                select(Subscription, User)
                .join(User, User.id == Subscription.user_id)
                .where(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.ends_at > now,
                )
            )
            for sub, user in result.all():
                days_left = (sub.ends_at - now).days
                if days_left not in REMINDER_DAYS:
                    continue
                key = f"reminder:{user.id}:{days_left}:{sub.ends_at.date()}"
                from shared.redis_client import get_redis

                redis = await get_redis()
                if await redis.exists(key):
                    continue

                lang = user.language if user.language in ("ru", "en", "ua") else "en"
                messages = {
                    "ru": f"⏳ Подписка истекает через {days_left} дн. ({sub.ends_at.date()})",
                    "en": f"⏳ Subscription expires in {days_left} days ({sub.ends_at.date()})",
                    "ua": f"⏳ Підписка закінчується через {days_left} дн. ({sub.ends_at.date()})",
                }
                try:
                    await bot.send_message(user.telegram_id, messages[lang])
                    await redis.setex(key, 86400 * 2, "1")
                except Exception as exc:
                    logger.warning("Reminder failed %s: %s", user.telegram_id, exc)
    finally:
        await bot.session.close()
