from shared.yaml_config import load_yaml


def plan_price_usdt(plan: str) -> float:
    cfg = load_yaml("pricing.yaml")
    base = float(cfg.get("month_usdt", 15))
    discounts = cfg.get("discounts", {})
    if plan == "3m":
        return base * 3 * (1 - discounts.get("3m", 0.25))
    if plan == "12m":
        return base * 12 * (1 - discounts.get("12m", 0.50))
    return base


def plan_amount(plan: str, currency: str) -> float:
    cfg = load_yaml("pricing.yaml")
    usdt = plan_price_usdt(plan)
    if currency == "USDT":
        return round(usdt, 2)
    if currency == "TON":
        ton = float(cfg.get("month_ton", 0))
        if ton <= 0:
            return round(usdt, 2)
        mult = {"1m": 1, "3m": 3 * (1 - cfg.get("discounts", {}).get("3m", 0.25)), "12m": 12 * (1 - cfg.get("discounts", {}).get("12m", 0.50))}
        return round(ton * mult.get(plan, 1), 4)
    if currency == "BTC":
        btc = float(cfg.get("month_btc", 0))
        if btc <= 0:
            return round(usdt, 2)
        mult = {"1m": 1, "3m": 3 * (1 - cfg.get("discounts", {}).get("3m", 0.25)), "12m": 12 * (1 - cfg.get("discounts", {}).get("12m", 0.50))}
        return round(btc * mult.get(plan, 1), 8)
    return round(usdt, 2)
