from dataclasses import dataclass

from shared.signal_types import Bias, Confidence, SignalType


@dataclass
class SignalCandidate:
    type: SignalType
    symbol: str
    confidence: Confidence
    bias: Bias
    payload: dict
    cooldown_key: str
