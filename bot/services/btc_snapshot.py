import logging

from bot.services.snapshot_formatter import format_btc_snapshot
from worker.bybit.client import BybitClient

logger = logging.getLogger(__name__)
SYMBOL = "BTCUSDT"


async def build_btc_snapshot(lang: str) -> str | None:
    client = BybitClient()
    await client.start()
    try:
        ticker, _ = await client.get_ticker(SYMBOL)
        if not ticker:
            return None

        price = float(ticker.get("lastPrice") or 0)
        change_24h = float(ticker.get("price24hPcnt") or 0) * 100

        rates, _ = await client.get_funding_history(SYMBOL, limit=48)
        latest_funding = float(rates[0]["fundingRate"]) if rates else 0.0
        avg_funding = (
            sum(float(r["fundingRate"]) for r in rates[:9]) / min(len(rates), 9)
            if rates
            else 0.0
        )

        oi_list, _ = await client.get_open_interest(SYMBOL)
        oi_change = 0.0
        if len(oi_list) >= 2:
            latest_oi = float(oi_list[0]["openInterest"])
            prev_oi = float(oi_list[1]["openInterest"])
            if prev_oi:
                oi_change = (latest_oi - prev_oi) / prev_oi * 100

        klines, _ = await client.get_klines(SYMBOL, interval="60", limit=168)
        volume_ratio = 1.0
        price_change_1h = 0.0
        if len(klines) >= 2:
            last_close = float(klines[0][4])
            prev_close = float(klines[1][4])
            if prev_close:
                price_change_1h = (last_close - prev_close) / prev_close * 100
            current_vol = float(klines[0][5])
            hist_vols = [float(k[5]) for k in klines[1:169]]
            if hist_vols:
                median_vol = sorted(hist_vols)[len(hist_vols) // 2]
                if median_vol > 0:
                    volume_ratio = current_vol / median_vol

        data = {
            "symbol": SYMBOL,
            "price": f"{price:,.2f}",
            "change_24h": f"{change_24h:+.2f}",
            "funding_pct": latest_funding * 100,
            "avg_funding_pct": avg_funding * 100,
            "oi_change_pct": oi_change,
            "volume_ratio": volume_ratio,
            "price_change_1h": price_change_1h,
        }
        return format_btc_snapshot(lang, data)
    except Exception:
        logger.exception("BTC snapshot failed")
        return None
    finally:
        await client.close()
