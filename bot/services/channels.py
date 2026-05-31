from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.users import get_active_subscription
from db.models import User
from shared.yaml_config import load_yaml

MEMBER_STATUSES = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


@dataclass(frozen=True)
class RequiredChannel:
    chat_id: str
    title: str
    url: str


def get_required_channels() -> list[RequiredChannel]:
    cfg = load_yaml("app.yaml")
    raw = cfg.get("required_channels") or []
    channels: list[RequiredChannel] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        chat_id = str(item.get("id") or item.get("username") or "").strip()
        url = str(item.get("url") or "").strip()
        if not chat_id or not url:
            continue
        title = str(item.get("title") or chat_id).strip()
        channels.append(RequiredChannel(chat_id=chat_id, title=title, url=url))
    return channels


async def channel_gate_required(session: AsyncSession, user: User) -> bool:
    if user.consented_at:
        return False
    if user.channels_verified_at:
        return False
    if not get_required_channels():
        return False
    if await get_active_subscription(session, user.id):
        return False
    return True


async def check_user_subscribed(bot: Bot, telegram_id: int) -> tuple[bool, list[str]]:
    channels = get_required_channels()
    if not channels:
        return True, []

    missing: list[str] = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel.chat_id, telegram_id)
            if member.status not in MEMBER_STATUSES:
                missing.append(channel.title)
        except TelegramBadRequest:
            missing.append(channel.title)
    return len(missing) == 0, missing
