from bot.i18n import t


def format_btc_snapshot(lang: str, data: dict) -> str:
    lang = lang if lang in ("ru", "en", "ua") else "en"
    lines = [
        t(lang, "btc_snapshot_title"),
        "",
        f"<b>{data['symbol']}</b>",
        t(
            lang,
            "btc_snapshot_price",
            price=data["price"],
            change_24h=data["change_24h"],
        ),
        t(
            lang,
            "btc_snapshot_funding",
            funding_pct=data["funding_pct"],
            avg_24h_pct=data["avg_funding_pct"],
        ),
        t(
            lang,
            "btc_snapshot_oi",
            oi_change_pct=data["oi_change_pct"],
        ),
        t(
            lang,
            "btc_snapshot_volume",
            volume_ratio=data["volume_ratio"],
            price_change_1h=data["price_change_1h"],
        ),
    ]
    return "\n".join(lines)
