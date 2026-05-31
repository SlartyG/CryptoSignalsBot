from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards import back_keyboard, pairs_keyboard, settings_keyboard
from bot.services.settings import get_settings_map, toggle_signal_type, toggle_symbol
from bot.services.users import get_or_create_user, user_tier
from db.models import UserTier
from shared.universe import get_active_symbols

router = Router()


def _settings_list(lang: str, settings_map: dict[str, bool]) -> str:
    labels = {
        "funding": "Funding",
        "oi_price": "OI+Price",
        "liquidation": "Liquidation",
        "volume": "Volume",
    }
    lines = []
    for key, label in labels.items():
        icon = t(lang, "signal_on") if settings_map.get(key, True) else t(lang, "signal_off")
        lines.append(f"{icon} {label}")
    return "\n".join(lines)


@router.callback_query(F.data == "menu:settings")
async def menu_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    lang = user.language
    settings_map = await get_settings_map(session, user.id)
    tier = await user_tier(session, user)
    is_paid = tier == UserTier.PAID

    await callback.message.edit_text(
        t(lang, "settings_text", settings_list=_settings_list(lang, settings_map)),
        reply_markup=settings_keyboard(lang, settings_map, is_paid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set:toggle:"))
async def toggle_setting(callback: CallbackQuery, session: AsyncSession) -> None:
    signal_type = callback.data.split(":")[2]
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    await toggle_signal_type(session, user.id, signal_type)
    await session.commit()

    lang = user.language
    settings_map = await get_settings_map(session, user.id)
    tier = await user_tier(session, user)
    await callback.message.edit_text(
        t(lang, "settings_text", settings_list=_settings_list(lang, settings_map)),
        reply_markup=settings_keyboard(lang, settings_map, tier == UserTier.PAID),
    )
    await callback.answer()


@router.callback_query(F.data == "set:pairs")
async def settings_pairs(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    tier = await user_tier(session, user)
    if tier != UserTier.PAID:
        await callback.answer(t(user.language, "not_implemented"), show_alert=True)
        return

    universe = await get_active_symbols(session)
    from sqlalchemy import select
    from db.models import UserSignalSetting

    result = await session.execute(
        select(UserSignalSetting).where(
            UserSignalSetting.user_id == user.id,
            UserSignalSetting.signal_type == "symbols",
        )
    )
    setting = result.scalar_one_or_none()
    selected = list(setting.symbols) if setting and setting.symbols else universe

    lang = user.language
    pairs_lines = "\n".join(f"{'✅' if s in selected else '⬜'} {s}" for s in universe)
    await callback.message.edit_text(
        t(lang, "settings_pairs_text", pairs_list=pairs_lines),
        reply_markup=pairs_keyboard(lang, universe, selected),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set:sym:"))
async def toggle_pair(callback: CallbackQuery, session: AsyncSession) -> None:
    symbol = callback.data.split(":")[2]
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    universe = await get_active_symbols(session)
    selected = await toggle_symbol(session, user.id, symbol, universe)
    await session.commit()

    lang = user.language
    pairs_lines = "\n".join(f"{'✅' if s in selected else '⬜'} {s}" for s in universe)
    await callback.message.edit_text(
        t(lang, "settings_pairs_text", pairs_list=pairs_lines),
        reply_markup=pairs_keyboard(lang, universe, selected),
    )
    await callback.answer()
