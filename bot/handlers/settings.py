import math

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards import back_keyboard, language_keyboard, pairs_keyboard, settings_keyboard
from bot.services.pairs_prefs import get_pairs_sort, set_pairs_sort
from bot.services.settings import (
    get_selected_symbols,
    get_settings_map,
    toggle_signal_type,
    toggle_symbol,
)
from bot.services.users import get_or_create_user, user_tier
from db.models import UserTier
from shared.signal_types import PAIRS_PAGE_SIZE
from shared.universe import get_active_symbols, get_universe_entries, sort_symbols

router = Router()


def _settings_list(lang: str, settings_map: dict[str, bool]) -> str:
    labels = {
        "funding": t(lang, "signal_type_funding"),
        "oi_price": t(lang, "signal_type_oi"),
        "liquidation": t(lang, "signal_type_liq"),
        "volume": t(lang, "signal_type_volume"),
    }
    lines = []
    for key, label in labels.items():
        icon = t(lang, "signal_on") if settings_map.get(key, True) else t(lang, "signal_off")
        lines.append(f"{icon} {label}")
    return "\n".join(lines)


async def _sorted_universe(session: AsyncSession, user_id: int, sort_mode: str | None = None) -> tuple[list[str], dict[str, int]]:
    entries = await get_universe_entries(session)
    if not entries:
        symbols = await get_active_symbols(session)
        rank_map = {s: i + 1 for i, s in enumerate(symbols)}
        return symbols, rank_map
    rank_map = {sym: rank for sym, rank, _ in entries}
    symbols = [sym for sym, _, _ in entries]
    sort_mode = sort_mode or await get_pairs_sort(user_id)
    return sort_symbols(symbols, sort_mode, rank_map), rank_map


async def _render_pairs(
    callback: CallbackQuery,
    session: AsyncSession,
    user,
    page: int,
    sort_mode: str,
) -> None:
    universe, _ = await _sorted_universe(session, user.id, sort_mode)
    selected = await get_selected_symbols(session, user.id, universe)
    total_pages = max(1, math.ceil(len(universe) / PAIRS_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    lang = user.language

    start = page * PAIRS_PAGE_SIZE
    page_symbols = universe[start : start + PAIRS_PAGE_SIZE]
    pairs_lines = "\n".join(f"{'✅' if s in selected else '⬜'} {s}" for s in page_symbols)

    await callback.message.edit_text(
        t(
            lang,
            "settings_pairs_text",
            pairs_list=pairs_lines,
            page=page + 1,
            total_pages=total_pages,
            selected_count=len(selected),
        ),
        reply_markup=pairs_keyboard(lang, universe, selected, page, sort_mode, total_pages),
    )


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


@router.callback_query(F.data == "set:language")
async def settings_language(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    lang = user.language
    await callback.message.edit_text(
        t(lang, "choose_language"),
        reply_markup=language_keyboard(return_to="settings"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set:pairs:"))
async def settings_pairs(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    if len(parts) >= 3 and parts[2] == "noop":
        await callback.answer()
        return

    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    tier = await user_tier(session, user)
    if tier != UserTier.PAID:
        await callback.answer(t(user.language, "pairs_paid_only"), show_alert=True)
        return

    page = int(parts[2]) if len(parts) > 2 else 0
    sort_mode = parts[3] if len(parts) > 3 else await get_pairs_sort(user.id)
    await set_pairs_sort(user.id, sort_mode)
    await _render_pairs(callback, session, user, page, sort_mode)
    await callback.answer()


@router.callback_query(F.data.startswith("set:sym:"))
async def toggle_pair(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    symbol = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0
    sort_mode = parts[4] if len(parts) > 4 else await get_pairs_sort(
        (await get_or_create_user(session, callback.from_user.id, callback.from_user.username)).id
    )

    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    tier = await user_tier(session, user)
    if tier != UserTier.PAID:
        await callback.answer(t(user.language, "pairs_paid_only"), show_alert=True)
        return

    universe = await get_active_symbols(session)
    await toggle_symbol(session, user.id, symbol, universe)
    await session.commit()

    await _render_pairs(callback, session, user, page, sort_mode)
    await callback.answer()
