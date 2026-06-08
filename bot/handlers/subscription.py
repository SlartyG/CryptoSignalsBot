from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards import (
    currency_keyboard,
    invoice_pay_keyboard,
    provider_keyboard,
    subscription_keyboard,
)
from bot.services.analytics import track
from bot.services.crypto_pay import CryptoPayClient
from bot.services.payment_verify import payment_payload
from bot.services.subscriptions import expire_user_pending_payments
from bot.services.users import get_or_create_user, get_active_subscription
from bot.services.xrocket_pay import XRocketPayClient
from db.models import Payment, PaymentProvider, PaymentStatus
from shared.pricing import plan_amount, plan_price_usdt

router = Router()


@router.callback_query(F.data == "menu:subscription")
async def menu_subscription(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    lang = user.language
    await track(session, user.id, "menu_subscription_open")
    sub = await get_active_subscription(session, user.id)

    if sub:
        status = t(lang, "sub_status_active")
        ends_at = sub.ends_at.strftime("%Y-%m-%d")
    else:
        status = t(lang, "sub_status_none")
        ends_at = "—"

    await session.commit()
    await callback.message.edit_text(
        t(lang, "subscription_text", status=status, ends_at=ends_at),
        reply_markup=subscription_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def choose_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    plan = callback.data.split(":")[1]
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    lang = user.language
    await callback.message.edit_text(
        t(lang, "subscription_text", status=t(lang, "sub_status_none"), ends_at="—")
        + f"\n\n{t(lang, 'plan_selected', plan=plan)}",
        reply_markup=currency_keyboard(lang, plan),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def choose_provider(callback: CallbackQuery, session: AsyncSession) -> None:
    _, plan, currency = callback.data.split(":")
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    lang = user.language
    keyboard = provider_keyboard(lang, plan, currency)
    if not keyboard:
        await callback.answer(t(lang, "pay_not_configured"), show_alert=True)
        return

    await callback.message.edit_text(
        t(lang, "subscription_text", status=t(lang, "sub_status_none"), ends_at="—")
        + f"\n\n{t(lang, 'plan_selected', plan=plan)}"
        + f"\n{t(lang, 'currency_selected', currency=currency)}"
        + f"\n\n{t(lang, 'choose_provider')}",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("provider:"))
async def create_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    _, plan, currency, provider_name = callback.data.split(":")
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    lang = user.language
    amount = plan_amount(plan, currency)
    amount_usdt = plan_price_usdt(plan)
    payload = payment_payload(user.id, plan)
    description = f"CryptoSignalsBot {plan}"

    try:
        if provider_name == PaymentProvider.CRYPTO_PAY:
            client = CryptoPayClient()
            if not client._token:
                await callback.answer(t(lang, "pay_not_configured"), show_alert=True)
                return
            invoice = await client.create_invoice(
                amount=amount,
                currency=currency,
                description=description,
                payload=payload,
            )
            invoice_id = str(invoice["invoice_id"])
            url = invoice.get("bot_invoice_url") or invoice.get("pay_url", "")
            provider = PaymentProvider.CRYPTO_PAY
        elif provider_name == PaymentProvider.XROCKET:
            client = XRocketPayClient()
            if not client._token:
                await callback.answer(t(lang, "pay_not_configured"), show_alert=True)
                return
            invoice = await client.create_invoice(
                amount=amount,
                currency=currency,
                description=description,
                payload=payload,
            )
            invoice_id = str(invoice["id"])
            url = invoice.get("link", "")
            provider = PaymentProvider.XROCKET
        else:
            await callback.answer(t(lang, "pay_not_configured"), show_alert=True)
            return
    except Exception as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await expire_user_pending_payments(session, user.id)

    payment = Payment(
        user_id=user.id,
        invoice_id=invoice_id,
        provider=provider,
        amount=amount,
        currency=currency,
        amount_usdt=amount_usdt,
        plan=plan,
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    await track(
        session,
        user.id,
        "payment_invoice_created",
        plan=plan,
        currency=currency,
        amount_usdt=amount_usdt,
        provider=provider,
    )
    await session.commit()

    if not url:
        await callback.answer(t(lang, "invoice_no_url"), show_alert=True)
        return

    await callback.message.edit_text(
        t(lang, "invoice_created"),
        reply_markup=invoice_pay_keyboard(lang, url),
    )
    await callback.answer()
