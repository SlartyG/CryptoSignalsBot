import json
import logging
import time

from shared.redis_client import get_redis
logger = logging.getLogger(__name__)

QUEUE_KEY = "notify:queue"
PAYLOAD_PREFIX = "notify:payload:"

DELIVER_SCALE = 10**10
PRIORITY_SCALE = 10**6


def _queue_score(deliver_at: float, priority: int, signal_id: int) -> float:
    return deliver_at * DELIVER_SCALE + priority * PRIORITY_SCALE + signal_id


async def enqueue(
    user_id: int,
    telegram_id: int,
    signal_id: int,
    priority: int,
    text: str,
    *,
    deliver_at: float | None = None,
) -> None:
    redis = await get_redis()
    if deliver_at is None:
        deliver_at = time.time()
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
            "deliver_at": deliver_at,
        }),
    )
    score = _queue_score(deliver_at, priority, signal_id)
    await redis.zadd(QUEUE_KEY, {payload_key: score})


async def pop_next() -> dict | None:
    redis = await get_redis()
    now = time.time()
    max_score = _queue_score(now, 2, 10**9)
    items = await redis.zrangebyscore(QUEUE_KEY, "-inf", max_score, start=0, num=1)
    if not items:
        return None
    payload_key = items[0]
    raw = await redis.get(payload_key)
    await redis.zrem(QUEUE_KEY, payload_key)
    await redis.delete(payload_key)
    if not raw:
        return None
    return json.loads(raw)
