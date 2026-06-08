from db.models import SignalLog
from shared.signal_types import SignalType

TYPE_LABELS = {
    "ru": {
        SignalType.FUNDING: "Funding Extreme",
        SignalType.OI_PRICE: "OI + Price",
        SignalType.LIQUIDATION: "Liquidation Spike",
        SignalType.VOLUME: "Volume Spike",
    },
    "en": {
        SignalType.FUNDING: "Funding Extreme",
        SignalType.OI_PRICE: "OI + Price",
        SignalType.LIQUIDATION: "Liquidation Spike",
        SignalType.VOLUME: "Volume Spike",
    },
    "ua": {
        SignalType.FUNDING: "Funding Extreme",
        SignalType.OI_PRICE: "OI + Price",
        SignalType.LIQUIDATION: "Liquidation Spike",
        SignalType.VOLUME: "Volume Spike",
    },
}

BIAS_LABELS = {
    "ru": {"bullish": "бычий bias", "bearish": "медвежий bias", "neutral": "нейтрально"},
    "en": {"bullish": "bullish bias", "bearish": "bearish bias", "neutral": "neutral"},
    "ua": {"bullish": "бичий bias", "bearish": "ведмежий bias", "neutral": "нейтрально"},
}

BIAS_EMOJI = {
    "bullish": "🟢",
    "bearish": "🔴",
    "neutral": "⚪",
}


def _display_symbol(symbol: str) -> str:
    if symbol.endswith("USDT"):
        return symbol[:-4]
    return symbol


def format_signal_message(lang: str, signal: SignalLog) -> str:
    lang = lang if lang in ("ru", "en", "ua") else "en"
    payload = signal.payload_json
    bias = payload.get("bias", "neutral")
    stype = SignalType(signal.type)

    display = _display_symbol(signal.symbol)
    emoji = BIAS_EMOJI.get(bias, "⚪")
    lines = [f"{emoji} #{display} · {TYPE_LABELS[lang].get(stype, signal.type)}"]

    if stype == SignalType.FUNDING:
        lines.append(
            f"📊 Funding: {payload['funding_pct']:+.3f}% · avg 24h: {payload['avg_24h_pct']:+.3f}%"
        )
    elif stype == SignalType.OI_PRICE:
        lines.append(
            f"📊 OI: {payload['oi_change_pct']:+.1f}% · Price 1h: {payload['price_change_pct']:+.1f}%"
        )
        lines.append(f"📌 Pattern: {payload.get('pattern', '—')}")
    elif stype == SignalType.LIQUIDATION:
        lines.append(f"📊 Liquidated: ${payload['total_usd']:,.0f} ({payload['window_minutes']}m)")
        lines.append(f"📌 Dominant: {payload.get('dominant_side', '—')} liquidated")
    elif stype == SignalType.VOLUME:
        lines.append(f"📊 Volume: {payload['volume_ratio']:.1f}× median")
        lines.append(f"📌 Price Δ: {payload.get('price_change_pct', 0):+.1f}%")

    lines.append(f"📈 {BIAS_LABELS[lang].get(bias, bias)}")
    lines.append(f"⚡ {signal.confidence}")
    return "\n".join(lines)
