from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.i18n import t
from bot.services.channels import RequiredChannel, get_required_channels
from shared.signal_types import SignalType


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            ],
            [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang:ua")],
        ]
    )


def consent_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "consent_accept"),
                    callback_data="consent:accept",
                )
            ],
        ]
    )


def channels_keyboard(lang: str, channels: list[RequiredChannel] | None = None) -> InlineKeyboardMarkup:
    items = channels if channels is not None else get_required_channels()
    rows: list[list[InlineKeyboardButton]] = []
    for channel in items:
        rows.append([InlineKeyboardButton(text=channel.title, url=channel.url)])
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "btn_check_subscription"),
                callback_data="channels:check",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_profile"), callback_data="menu:profile")],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_subscription"),
                    callback_data="menu:subscription",
                )
            ],
            [InlineKeyboardButton(text=t(lang, "btn_settings"), callback_data="menu:settings")],
            [
                InlineKeyboardButton(text=t(lang, "btn_faq"), callback_data="menu:faq"),
                InlineKeyboardButton(text=t(lang, "btn_support"), callback_data="menu:support"),
            ],
        ]
    )


def back_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:main")]
        ]
    )


def subscription_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_buy_1m"), callback_data="buy:1m"),
                InlineKeyboardButton(text=t(lang, "btn_buy_3m"), callback_data="buy:3m"),
            ],
            [InlineKeyboardButton(text=t(lang, "btn_buy_12m"), callback_data="buy:12m")],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:main")],
        ]
    )


def currency_keyboard(lang: str, plan: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "pay_currency_usdt"),
                    callback_data=f"pay:{plan}:USDT",
                ),
                InlineKeyboardButton(
                    text=t(lang, "pay_currency_ton"),
                    callback_data=f"pay:{plan}:TON",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "pay_currency_btc"),
                    callback_data=f"pay:{plan}:BTC",
                )
            ],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:subscription")],
        ]
    )


def settings_keyboard(lang: str, settings_map: dict[str, bool], is_paid: bool) -> InlineKeyboardMarkup:
    rows = []
    labels = {
        SignalType.FUNDING.value: "Funding",
        SignalType.OI_PRICE.value: "OI+Price",
        SignalType.LIQUIDATION.value: "Liq",
        SignalType.VOLUME.value: "Volume",
    }
    for st, label in labels.items():
        on = settings_map.get(st, True)
        icon = t(lang, "signal_on") if on else t(lang, "signal_off")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {label}",
                    callback_data=f"set:toggle:{st}",
                )
            ]
        )
    if is_paid:
        rows.append(
            [InlineKeyboardButton(text="📊 Pairs", callback_data="set:pairs")]
        )
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pairs_keyboard(lang: str, universe: list[str], selected: list[str]) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for sym in universe:
        mark = "✅" if sym in selected else "⬜"
        row.append(InlineKeyboardButton(text=f"{mark} {sym}", callback_data=f"set:sym:{sym}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
