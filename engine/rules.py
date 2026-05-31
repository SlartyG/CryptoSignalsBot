from shared.signal_types import ALWAYS_SYMBOLS, Bias, Confidence, SignalType
from shared.yaml_config import load_yaml


def _is_major(symbol: str) -> bool:
    return symbol in ("BTCUSDT", "ETHUSDT")


def check_funding(symbol: str, rates: list[dict]) -> "SignalCandidate | None":
    from engine.models import SignalCandidate

    if not rates:
        return None

    cfg = load_yaml("signals.yaml")["funding"]
    medium = cfg["medium_threshold"]
    high = cfg["high_threshold"]
    spike_mult = cfg["spike_multiplier"]

    latest = float(rates[0]["fundingRate"])
    avg = sum(float(r["fundingRate"]) for r in rates[:9]) / min(len(rates), 9)
    abs_rate = abs(latest)

    confidence = None
    if abs_rate >= high or (abs_rate >= medium and abs_rate >= abs(avg) * spike_mult):
        confidence = Confidence.HIGH
    elif abs_rate >= medium:
        confidence = Confidence.MEDIUM
    else:
        return None

    bias = Bias.BEARISH if latest > 0 else Bias.BULLISH
    return SignalCandidate(
        type=SignalType.FUNDING,
        symbol=symbol,
        confidence=confidence,
        bias=bias,
        payload={
            "funding_rate": latest,
            "funding_pct": latest * 100,
            "avg_24h": avg,
            "avg_24h_pct": avg * 100,
            "pattern": "extreme_funding",
        },
        cooldown_key=f"{symbol}:funding",
    )


def check_oi_price(
    symbol: str, oi_list: list[dict], price_change_pct: float
) -> "SignalCandidate | None":
    from engine.models import SignalCandidate

    if len(oi_list) < 2:
        return None

    cfg = load_yaml("signals.yaml")["oi"]
    oi_thresh = cfg["change_1h_pct"] if _is_major(symbol) else cfg["change_1h_pct"] + 4
    price_thresh = cfg["price_change_1h_pct"] if _is_major(symbol) else cfg["price_change_1h_pct"] + 1
    liq_drop = cfg["liquidation_oi_drop_pct"]

    newest = float(oi_list[0]["openInterest"])
    oldest = float(oi_list[-1]["openInterest"])
    if oldest == 0:
        return None
    oi_change = (newest - oldest) / oldest * 100

    pattern = None
    bias = Bias.NEUTRAL
    confidence = Confidence.MEDIUM

    if oi_change >= oi_thresh and price_change_pct >= price_thresh:
        pattern = "trend_long"
        bias = Bias.BULLISH
    elif oi_change >= oi_thresh and price_change_pct <= -price_thresh:
        pattern = "trend_short"
        bias = Bias.BEARISH
    elif oi_change <= -liq_drop and abs(price_change_pct) >= price_thresh + 1:
        pattern = "liquidation_flush"
        bias = Bias.NEUTRAL
        confidence = Confidence.HIGH
    else:
        return None

    return SignalCandidate(
        type=SignalType.OI_PRICE,
        symbol=symbol,
        confidence=confidence,
        bias=bias,
        payload={
            "oi_change_pct": oi_change,
            "price_change_pct": price_change_pct,
            "pattern": pattern,
        },
        cooldown_key=f"{symbol}:oi_price:{pattern}",
    )


def check_volume(symbol: str, klines: list[list], current_volume: float) -> "SignalCandidate | None":
    from engine.models import SignalCandidate
    from datetime import datetime, timezone

    if len(klines) < 24:
        return None

    cfg = load_yaml("signals.yaml")["volume"]
    spike = cfg["spike_multiplier"]
    high_spike = cfg["high_spike_multiplier"]
    min_price = cfg["min_price_change_pct"]

    now = datetime.now(timezone.utc)
    hour = now.hour

    volumes_by_hour: dict[int, list[float]] = {}
    for row in klines:
        ts_ms = int(row[0])
        vol = float(row[5])
        h = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).hour
        volumes_by_hour.setdefault(h, []).append(vol)

    hour_vols = volumes_by_hour.get(hour, [])
    if not hour_vols:
        return None
    median = sorted(hour_vols)[len(hour_vols) // 2]
    if median <= 0:
        return None

    ratio = current_volume / median
    if ratio < spike:
        return None

    last_close = float(klines[0][4])
    prev_close = float(klines[1][4]) if len(klines) > 1 else last_close
    price_change = abs((last_close - prev_close) / prev_close * 100) if prev_close else 0

    confidence = Confidence.MEDIUM
    if ratio >= high_spike and price_change >= min_price:
        confidence = Confidence.HIGH

    bias = Bias.BULLISH if last_close >= prev_close else Bias.BEARISH
    return SignalCandidate(
        type=SignalType.VOLUME,
        symbol=symbol,
        confidence=confidence,
        bias=bias,
        payload={
            "volume_ratio": ratio,
            "median_volume": median,
            "current_volume": current_volume,
            "price_change_pct": price_change,
        },
        cooldown_key=f"{symbol}:volume",
    )


def check_liquidation(
    symbol: str,
    total_usd: float,
    long_usd: float,
    short_usd: float,
    avg_24h: float,
) -> "SignalCandidate | None":
    from engine.models import SignalCandidate

    cfg = load_yaml("signals.yaml")["liquidation"]
    medium = cfg["medium_usd"]
    high = cfg["high_usd"]

    confidence = None
    if total_usd >= high or (avg_24h > 0 and total_usd >= 3 * avg_24h):
        confidence = Confidence.HIGH
    elif total_usd >= medium:
        confidence = Confidence.MEDIUM
    else:
        return None

    if long_usd > short_usd:
        bias = Bias.BEARISH
        dominant = "longs"
    else:
        bias = Bias.BULLISH
        dominant = "shorts"

    return SignalCandidate(
        type=SignalType.LIQUIDATION,
        symbol=symbol,
        confidence=confidence,
        bias=bias,
        payload={
            "total_usd": total_usd,
            "long_usd": long_usd,
            "short_usd": short_usd,
            "dominant_side": dominant,
            "window_minutes": cfg["window_minutes"],
        },
        cooldown_key=f"{symbol}:liquidation",
    )
