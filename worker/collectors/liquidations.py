import asyncio
import json
import logging
import time
from collections import defaultdict

import websockets
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import SessionLocal
from engine.rules import check_liquidation
from engine.signal_engine import emit_signal, record_metric
from shared.yaml_config import load_yaml
from shared.universe import get_active_symbols

logger = logging.getLogger(__name__)

BYBIT_WS = "wss://stream.bybit.com/v5/public/linear"
WS_CHUNK_SIZE = 40

_liq_buffer: dict[str, list[tuple[float, str, float]]] = defaultdict(list)
_avg_cache: dict[str, float] = {}


def _prune_buffer(symbol: str, window_sec: int) -> None:
    cutoff = time.time() - window_sec
    _liq_buffer[symbol] = [(ts, side, usd) for ts, side, usd in _liq_buffer[symbol] if ts >= cutoff]


async def _evaluate_symbol(session: AsyncSession, symbol: str) -> None:
    cfg = load_yaml("signals.yaml")["liquidation"]
    window_min = cfg["window_minutes"]
    window_sec = window_min * 60
    _prune_buffer(symbol, window_sec)

    total = long_usd = short_usd = 0.0
    for _, side, usd in _liq_buffer[symbol]:
        total += usd
        if side == "Buy":
            long_usd += usd
        else:
            short_usd += usd

    avg = _avg_cache.get(symbol, 0)
    candidate = check_liquidation(symbol, total, long_usd, short_usd, avg)
    if candidate:
        await emit_signal(session, candidate)
        _liq_buffer[symbol].clear()
        await session.commit()


def _chunk_symbols(symbols: list[str], size: int) -> list[list[str]]:
    return [symbols[i : i + size] for i in range(0, len(symbols), size)]


async def _run_ws_chunk(symbols: list[str], stop_event: asyncio.Event) -> None:
    topics = [f"allLiquidation.{s}" for s in symbols]
    subscribe_msg = {"op": "subscribe", "args": topics}

    async with websockets.connect(BYBIT_WS, ping_interval=20) as ws:
        await ws.send(json.dumps(subscribe_msg))
        logger.info("Liquidation WS subscribed to %d symbols", len(symbols))

        last_eval = time.time()
        while not stop_event.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            except asyncio.TimeoutError:
                if time.time() - last_eval > 30:
                    async with SessionLocal() as session:
                        for sym in symbols:
                            await _evaluate_symbol(session, sym)
                    last_eval = time.time()
                continue

            msg = json.loads(raw)
            if msg.get("topic", "").startswith("allLiquidation."):
                symbol = msg["topic"].split(".")[-1]
                for item in msg.get("data", []):
                    size = float(item.get("v", 0))
                    price = float(item.get("p", 0))
                    side = item.get("S", "Buy")
                    usd = size * price
                    _liq_buffer[symbol].append((time.time(), side, usd))

            if time.time() - last_eval > 60:
                async with SessionLocal() as session:
                    for sym in set(_liq_buffer.keys()):
                        await _evaluate_symbol(session, sym)
                last_eval = time.time()


async def liquidation_listener(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with SessionLocal() as session:
                symbols = await get_active_symbols(session)
            if not symbols:
                symbols = ["BTCUSDT"]

            chunks = _chunk_symbols(symbols, WS_CHUNK_SIZE)
            tasks = [
                asyncio.create_task(_run_ws_chunk(chunk, stop_event))
                for chunk in chunks
            ]
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                for t in tasks:
                    t.cancel()
                raise

        except Exception as exc:
            logger.exception("Liquidation WS error: %s", exc)
            await record_metric_standalone("liquidations", False, error=str(exc))
            await asyncio.sleep(5)


async def record_metric_standalone(name: str, success: bool, error: str | None = None) -> None:
    async with SessionLocal() as session:
        await record_metric(session, name, success, error=error)
        await session.commit()
