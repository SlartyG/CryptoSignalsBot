import json
import logging

from shared.redis_client import get_redis

logger = logging.getLogger(__name__)

QUEUE_KEY = "notify:queue"
PAYLOAD_PREFIX = "notify:payload:"


async def enqueue(user_id: int, telegram_id: int, signal_id: int, priority: int, text: str) -> None:
    redis = await get_redis()
    payload_key = f"{PAYLOAD_PREFIX}{signal_id}:{user_id}"
    await redis.setex(
        payload_key,
        3600,
        json.dumps({
            "telegram_id": telegram_id,
            "text": text,
            "signal_id": signal_id,
            "user_id": user_id,
            "priority": priority,
        }),
    )
    score = priority * 1_000_000_000_000 + signal_id
    await redis.zadd(QUEUE_KEY, {payload_key: score})


async def pop_next() -> dict | None:
    redis = await get_redis()
    items = await redis.zrange(QUEUE_KEY, 0, 0)
    if not items:
        return None
    payload_key = items[0]
    raw = await redis.get(payload_key)
    await redis.zrem(QUEUE_KEY, payload_key)
    await redis.delete(payload_key)
    if not raw:
        return None
    return json.loads(raw)
