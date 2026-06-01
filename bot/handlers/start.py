from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards import (
    back_keyboard,
    channels_keyboard,
    consent_keyboard,
    language_keyboard,
    main_menu_keyboard,
)
from bot.services.analytics import track
from bot.services.btc_snapshot import build_btc_snapshot
from bot.services.channels import channel_gate_required, check_user_subscribed
from bot.services.users import get_or_create_user, user_tier
from bot.text_html import link
from shared.yaml_config import load_yaml

router = Router()


def _links(lang: str) -> dict[str, str]:
    cfg = load_yaml("app.yaml")
    links = cfg.get("links", {})
    suffix = lang if lang in ("ru", "en", "ua") else "en"
    return {
        "offer_url": links.get(f"offer_{suffix}", links.get("offer_en", "#")),
        "privacy_url": links.get(f"privacy_{suffix}", links.get("privacy_en", "#")),
        "faq_url": links.get(f"faq_{suffix}", links.get("faq_en", "#")),
    }


def _consent_html(lang: str) -> str:
    links = _links(lang)
    offer = link(links["offer_url"], t(lang, "consent_offer_label"))
    privacy = link(links["privacy_url"], t(lang, "consent_privacy_label"))
    return t(lang, "consent_text", offer_link=offer, privacy_link=privacy)


def _tier_label(lang: str, tier) -> str:
    from db.models import UserTier

    return t(lang, "tier_paid" if tier == UserTier.PAID else "tier_free")


async def _show_consent(target: Message, lang: str) -> None:
    await target.answer(
        _consent_html(lang),
        reply_markup=consent_keyboard(lang),
        disable_web_page_preview=True,
    )


async def _show_channels(target: Message, lang: str) -> None:
    await target.answer(
        t(lang, "channels_text"),
        reply_markup=channels_keyboard(lang),
        disable_web_page_preview=True,
    )


async def _continue_onboarding(
    target: Message,
    session: AsyncSession,
    user,
    *,
    edit: Message | None = None,
) -> None:
    lang = user.language
    if user.consented_at:
        tier = await user_tier(session, user)
        text = t(lang, "main_menu_text", tier=_tier_label(lang, tier), language=lang.upper())
        markup = main_menu_keyboard(lang)
        if edit:
            await edit.edit_text(text, reply_markup=markup)
        else:
            await target.answer(text, reply_markup=markup)
        return

    if await channel_gate_required(session, user):
        text = t(lang, "channels_text")
        markup = channels_keyboard(lang)
        if edit:
            await edit.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        else:
            await target.answer(text, reply_markup=markup, disable_web_page_preview=True)
        return

    text = _consent_html(lang)
    markup = consent_keyboard(lang)
    if edit:
        await edit.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await target.answer(text, reply_markup=markup, disable_web_page_preview=True)


async def _show_main_menu(message: Message, session: AsyncSession, user) -> None:
    await _continue_onboarding(message, session, user)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
    )
    await track(session, user.id, "bot_start")
    await session.commit()

    if user.consented_at:
        await _show_main_menu(message, session, user)
        return

    await message.answer(
        t(user.language, "start_welcome"),
        reply_markup=language_keyboard(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    lang = parts[1]
    return_to = parts[2] if len(parts) > 2 else None

    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
    )
    user.language = lang if lang in ("ru", "en", "ua") else "en"
    await track(session, user.id, "language_set", language=user.language)
    await session.commit()

    if return_to == "settings":
        from bot.handlers.settings import menu_settings

        await callback.answer(t(user.language, "language_set"))
        await menu_settings(callback, session)
        return

    await _continue_onboarding(callback.message, session, user, edit=callback.message)
    await callback.answer(t(user.language, "language_set"))


@router.callback_query(F.data == "channels:check")
async def check_channels(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
    )
    lang = user.language

    ok, missing = await check_user_subscribed(callback.bot, callback.from_user.id)
    if not ok:
        missing_text = ", ".join(missing)
        await callback.answer(
            t(lang, "channels_not_subscribed", channels=missing_text),
            show_alert=True,
        )
        return

    user.channels_verified_at = datetime.now(timezone.utc)
    await track(session, user.id, "channels_verified")
    await session.commit()

    await callback.answer(t(lang, "channels_verified"), show_alert=False)

    await callback.message.edit_text(
        _consent_html(lang),
        reply_markup=consent_keyboard(lang),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "consent:accept")
async def accept_consent(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
    )
    lang = user.language

    if await channel_gate_required(session, user):
        await callback.answer(t(lang, "channels_required"), show_alert=True)
        await _continue_onboarding(callback.message, session, user, edit=callback.message)
        return

    first_consent = not user.consented_at
    if not user.consented_at:
        user.consented_at = datetime.now(timezone.utc)
    if not user.channels_verified_at and not await channel_gate_required(session, user):
        user.channels_verified_at = datetime.now(timezone.utc)

    if first_consent:
        await track(session, user.id, "consent_accepted")
    await session.commit()

    await callback.message.delete()
    await _show_main_menu(callback.message, session, user)

    if first_consent and not user.welcome_snapshot_at:
        text = await build_btc_snapshot(lang)
        if text:
            await callback.bot.send_message(
                user.telegram_id,
                text,
                disable_web_page_preview=True,
            )
            user.welcome_snapshot_at = datetime.now(timezone.utc)
            await track(session, user.id, "welcome_btc_sent")
            await session.commit()

    await callback.answer()


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
    )
    if not user.consented_at:
        await callback.answer(t(user.language, "consent_required"), show_alert=True)
        return

    tier = await user_tier(session, user)
    lang = user.language
    await callback.message.edit_text(
        t(lang, "main_menu_text", tier=_tier_label(lang, tier), language=lang.upper()),
        reply_markup=main_menu_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def menu_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
    )
    lang = user.language
    tier = await user_tier(session, user)
    username = user.username or "—"
    created = user.created_at.strftime("%Y-%m-%d") if user.created_at else "—"

    await callback.message.edit_text(
        t(
            lang,
            "profile_text",
            telegram_id=user.telegram_id,
            username=username,
            language=lang.upper(),
            tier=_tier_label(lang, tier),
            created_at=created,
        ),
        reply_markup=back_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:alerts_guide")
async def menu_alerts_guide(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
    )
    lang = user.language
    await callback.message.edit_text(
        t(lang, "alerts_guide_text"),
        reply_markup=back_keyboard(lang),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data == "menu:faq")
async def menu_faq(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
    )
    lang = user.language
    links = _links(lang)
    faq_url = links["faq_url"]
    await callback.message.edit_text(
        t(lang, "faq_text", url=link(faq_url, faq_url)),
        reply_markup=back_keyboard(lang),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data == "menu:support")
async def menu_support(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
    )
    lang = user.language
    cfg = load_yaml("app.yaml")
    contact = cfg.get("support_contact", "@support")
    await callback.message.edit_text(
        t(lang, "support_text", contact=contact),
        reply_markup=back_keyboard(lang),
    )
    await callback.answer()


@router.message(Command("menu"))
async def cmd_menu(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
    )
    if not user.consented_at:
        await message.answer(t(user.language, "consent_required"))
        return
    await _show_main_menu(message, session, user)
