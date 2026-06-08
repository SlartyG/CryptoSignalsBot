from enum import StrEnum


class SignalType(StrEnum):
    FUNDING = "funding"
    OI_PRICE = "oi_price"
    LIQUIDATION = "liquidation"
    VOLUME = "volume"


class Confidence(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"


class Bias(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


ALWAYS_SYMBOLS = ("BTCUSDT", "ETHUSDT")
UNIVERSE_SIZE = 100
DEFAULT_SYMBOLS_COUNT = 10
FREE_DELAY_SEC = 60
PAIRS_PAGE_SIZE = 10
