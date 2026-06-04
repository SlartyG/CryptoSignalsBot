import logging

import httpx

from shared.config import settings

logger = logging.getLogger(__name__)

XROCKET_PAY_BASE = "https://pay.xrocket.exchange"

# Crypto Pay asset codes -> xRocket currency IDs (see GET /currencies/available)
CURRENCY_MAP = {
    "USDT": "USDT",
    "TON": "TONCOIN",
    "BTC": "BTC",
}


class XRocketPayClient:
    def __init__(self, token: str | None = None) -> None:
        self._token = token or settings.xrocket_pay_token

    def _headers(self) -> dict[str, str]:
        return {
            "Rocket-Pay-Key": self._token,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _asset(currency: str) -> str:
        return CURRENCY_MAP.get(currency, currency)

    async def create_invoice(
        self,
        amount: float,
        currency: str,
        description: str,
        payload: str,
    ) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{XROCKET_PAY_BASE}/tg-invoices",
                headers=self._headers(),
                json={
                    "amount": amount,
                    "currency": self._asset(currency),
                    "description": description,
                    "payload": payload,
                    "numPayments": 1,
                    "expiredIn": 3600,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "xRocket Pay error"))
            return data["data"]

    async def get_invoice(self, invoice_id: str) -> dict | None:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{XROCKET_PAY_BASE}/tg-invoices/{invoice_id}",
                headers=self._headers(),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "xRocket Pay error"))
            return data.get("data")
