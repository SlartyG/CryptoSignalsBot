import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BYBIT_BASE = "https://api.bybit.com"


class BybitClient:
    def __init__(self, base_url: str = BYBIT_BASE) -> None:
        self._base_url = base_url
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        assert self._client is not None
        started = time.perf_counter()
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.get(path, params=params)
                resp.raise_for_status()
                data = resp.json()
                if data.get("retCode") != 0:
                    raise RuntimeError(data.get("retMsg", "Bybit API error"))
                data["_latency_ms"] = int((time.perf_counter() - started) * 1000)
                return data
            except Exception as exc:
                last_exc = exc
                logger.warning("Bybit retry %s attempt %s: %s", path, attempt + 1, exc)
                await asyncio.sleep(1 + attempt)
        raise last_exc or RuntimeError("Bybit request failed")

    async def get_tickers_linear(self) -> list[dict]:
        data = await self._get("/v5/market/tickers", {"category": "linear"})
        return data["result"]["list"]

    async def get_funding_history(self, symbol: str, limit: int = 48) -> tuple[list[dict], int]:
        data = await self._get(
            "/v5/market/funding/history",
            {"category": "linear", "symbol": symbol, "limit": limit},
        )
        return data["result"]["list"], data["_latency_ms"]

    async def get_open_interest(
        self, symbol: str, interval: str = "5min", limit: int = 13
    ) -> tuple[list[dict], int]:
        data = await self._get(
            "/v5/market/open-interest",
            {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": interval,
                "limit": limit,
            },
        )
        return data["result"]["list"], data["_latency_ms"]

    async def get_klines(
        self, symbol: str, interval: str = "60", limit: int = 168
    ) -> tuple[list[list], int]:
        data = await self._get(
            "/v5/market/kline",
            {"category": "linear", "symbol": symbol, "interval": interval, "limit": limit},
        )
        return data["result"]["list"], data["_latency_ms"]

    async def get_ticker(self, symbol: str) -> tuple[dict, int]:
        data = await self._get("/v5/market/tickers", {"category": "linear", "symbol": symbol})
        items = data["result"]["list"]
        return items[0] if items else {}, data["_latency_ms"]
