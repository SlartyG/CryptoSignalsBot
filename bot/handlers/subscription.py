from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards import back_keyboard, currency_keyboard, subscription_keyboard
from bot.services.crypto_pay import CryptoPayClient
from bot.services.users import get_or_create_user, get_active_subscription
from db.models import Payment, PaymentStatus
from shared.pricing import plan_amount, plan_price_usdt

router = Router()


@router.callback_query(F.data == "menu:subscription")
async def menu_subscription(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    lang = user.language
    sub = await get_active_subscription(session, user.id)

    if sub:
        status = t(lang, "sub_status_active")
        ends_at = sub.ends_at.strftime("%Y-%m-%d")
    else:
        status = t(lang, "sub_status_none")
        ends_at = "—"

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
        + f"\n\nPlan: {plan}",
        reply_markup=currency_keyboard(lang, plan),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def create_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    _, plan, currency = callback.data.split(":")
    user = await get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    lang = user.language

    if not CryptoPayClient()._token:
        await callback.answer("Crypto Pay not configured", show_alert=True)
        return

    amount = plan_amount(plan, currency)
    amount_usdt = plan_price_usdt(plan)
    client = CryptoPayClient()

    try:
        invoice = await client.create_invoice(
            amount=amount,
            currency=currency,
            description=f"CryptoSignalsBot {plan}",
            payload=f"user:{user.id}:plan:{plan}",
        )
    except Exception as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    payment = Payment(
        user_id=user.id,
        invoice_id=str(invoice["invoice_id"]),
        amount=amount,
        currency=currency,
        amount_usdt=amount_usdt,
        plan=plan,
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    await session.commit()

    url = invoice.get("bot_invoice_url") or invoice.get("pay_url", "")
    await callback.message.edit_text(
        t(lang, "invoice_created", url=url),
        reply_markup=back_keyboard(lang),
        disable_web_page_preview=True,
    )
    await callback.answer()
