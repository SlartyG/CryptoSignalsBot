import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from bot.i18n import t
from db.models import User
from db.session import SessionLocal
from shared.config import settings

logger = logging.getLogger(__name__)


async def notify_payment_success(user_id: int, ends_at: datetime) -> None:
    if not settings.bot_token:
        return

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return
        telegram_id = user.telegram_id
        lang = user.language if user.language in ("ru", "en", "ua") else "en"

    ends_str = ends_at.strftime("%Y-%m-%d")
    text = t(lang, "payment_success", ends_at=ends_str)

    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(telegram_id, text)
    except Exception as exc:
        logger.warning("Payment notify failed for %s: %s", telegram_id, exc)
    finally:
        await bot.session.close()
