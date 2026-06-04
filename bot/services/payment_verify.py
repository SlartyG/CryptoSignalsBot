"""Validate provider invoice data before activating subscription."""

from db.models import Payment, PaymentProvider
from bot.services.xrocket_pay import CURRENCY_MAP

_AMOUNT_EPS = 0.02


def payment_payload(user_id: int, plan: str) -> str:
    return f"user:{user_id}:plan:{plan}"


def _amounts_match(expected: float, actual: float) -> bool:
    return abs(expected - actual) <= _AMOUNT_EPS


def verify_paid_invoice(payment: Payment, invoice: dict) -> str | None:
    """Return error reason string, or None if invoice matches our payment record."""
    expected_payload = payment_payload(payment.user_id, payment.plan)
    inv_payload = invoice.get("payload") or ""
    if inv_payload != expected_payload:
        return f"payload mismatch: {inv_payload!r}"

    if payment.provider == PaymentProvider.CRYPTO_PAY:
        asset = invoice.get("asset") or ""
        if asset != payment.currency:
            return f"currency mismatch: {asset}"
        try:
            paid_amount = float(invoice.get("amount", 0))
        except (TypeError, ValueError):
            return "invalid amount"
        if not _amounts_match(payment.amount, paid_amount):
            return f"amount mismatch: {paid_amount} != {payment.amount}"
        return None

    if payment.provider == PaymentProvider.XROCKET:
        expected_asset = CURRENCY_MAP.get(payment.currency, payment.currency)
        inv_currency = invoice.get("currency") or ""
        if inv_currency != expected_asset:
            return f"currency mismatch: {inv_currency}"
        try:
            paid_amount = float(invoice.get("amount", 0))
        except (TypeError, ValueError):
            return "invalid amount"
        if not _amounts_match(payment.amount, paid_amount):
            return f"amount mismatch: {paid_amount} != {payment.amount}"
        return None

    return f"unknown provider: {payment.provider}"
