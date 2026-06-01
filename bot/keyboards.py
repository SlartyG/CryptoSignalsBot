from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.i18n import t
from bot.services.channels import RequiredChannel, get_required_channels
from shared.signal_types import PAIRS_PAGE_SIZE, SignalType


def language_keyboard(return_to: str | None = None) -> InlineKeyboardMarkup:
    suffix = f":{return_to}" if return_to else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"lang:ru{suffix}"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data=f"lang:en{suffix}"),
            ],
            [InlineKeyboardButton(text="🇺🇦 Українська", callback_data=f"lang:ua{suffix}")],
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
                InlineKeyboardButton(
                    text=t(lang, "btn_alerts_guide"),
                    callback_data="menu:alerts_guide",
                ),
                InlineKeyboardButton(text=t(lang, "btn_faq"), callback_data="menu:faq"),
            ],
            [InlineKeyboardButton(text=t(lang, "btn_support"), callback_data="menu:support")],
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
        SignalType.FUNDING.value: t(lang, "signal_type_funding"),
        SignalType.OI_PRICE.value: t(lang, "signal_type_oi"),
        SignalType.LIQUIDATION.value: t(lang, "signal_type_liq"),
        SignalType.VOLUME.value: t(lang, "signal_type_volume"),
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
    rows.append(
        [InlineKeyboardButton(text=t(lang, "btn_language"), callback_data="set:language")]
    )
    if is_paid:
        rows.append(
            [InlineKeyboardButton(text=t(lang, "btn_pairs"), callback_data="set:pairs:0:vol")]
        )
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pairs_keyboard(
    lang: str,
    symbols: list[str],
    selected: list[str],
    page: int,
    sort_mode: str,
    total_pages: int,
) -> InlineKeyboardMarkup:
    start = page * PAIRS_PAGE_SIZE
    page_symbols: list[str] = []
    seen: set[str] = set()
    for sym in symbols[start : start + PAIRS_PAGE_SIZE]:
        if sym in seen:
            continue
        seen.add(sym)
        page_symbols.append(sym)
    # If DB had duplicates, backfill from next symbols so the page stays full.
    idx = start + PAIRS_PAGE_SIZE
    while len(page_symbols) < PAIRS_PAGE_SIZE and idx < len(symbols):
        sym = symbols[idx]
        idx += 1
        if sym not in seen:
            seen.add(sym)
            page_symbols.append(sym)

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for sym in page_symbols:
        mark = "✅" if sym in selected else "⬜"
        row.append(
            InlineKeyboardButton(
                text=f"{mark} {sym}",
                callback_data=f"set:sym:{sym}:{page}:{sort_mode}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    sort_label = t(lang, "pairs_sort_alpha" if sort_mode == "alpha" else "pairs_sort_vol")
    next_sort = "alpha" if sort_mode == "vol" else "vol"
    rows.append(
        [
            InlineKeyboardButton(
                text=sort_label,
                callback_data=f"set:pairs:{page}:{next_sort}",
            )
        ]
    )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"set:pairs:{page - 1}:{sort_mode}",
            )
        )
    nav.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="set:pairs:noop",
        )
    )
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"set:pairs:{page + 1}:{sort_mode}",
            )
        )
    rows.append(nav)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
