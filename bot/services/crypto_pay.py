import logging

import httpx

from shared.config import settings

logger = logging.getLogger(__name__)

CRYPTO_PAY_BASE = "https://pay.crypt.bot/api"


class CryptoPayClient:
    def __init__(self, token: str | None = None) -> None:
        self._token = token or settings.crypto_pay_token

    def _headers(self) -> dict:
        return {"Crypto-Pay-API-Token": self._token}

    async def create_invoice(
        self,
        amount: float,
        currency: str,
        description: str,
        payload: str,
    ) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{CRYPTO_PAY_BASE}/createInvoice",
                headers=self._headers(),
                json={
                    "asset": currency,
                    "amount": str(amount),
                    "description": description,
                    "payload": payload,
                    "expires_in": 3600,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("error", "Crypto Pay error"))
            return data["result"]

    async def get_invoices(self, invoice_ids: list[str]) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{CRYPTO_PAY_BASE}/getInvoices",
                headers=self._headers(),
                params={"invoice_ids": ",".join(invoice_ids)},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("error", "Crypto Pay error"))
            items = data.get("result", {}).get("items", [])
            return items if isinstance(items, list) else []
