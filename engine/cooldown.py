from shared.redis_client import get_redis
from shared.yaml_config import load_yaml


async def is_on_cooldown(cooldown_key: str) -> bool:
    redis = await get_redis()
    return bool(await redis.exists(f"cooldown:{cooldown_key}"))


async def set_cooldown(signal_type: str, cooldown_key: str) -> None:
    cfg = load_yaml("signals.yaml")
    minutes = cfg.get("cooldown_minutes", {}).get(signal_type, 60)
    redis = await get_redis()
    await redis.setex(f"cooldown:{cooldown_key}", minutes * 60, "1")
