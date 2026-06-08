from shared.redis_client import get_redis

PAIRS_SORT_KEY = "user:{user_id}:pairs_sort"
VALID_SORTS = ("vol", "alpha")


async def get_pairs_sort(user_id: int) -> str:
    redis = await get_redis()
    sort = await redis.get(PAIRS_SORT_KEY.format(user_id=user_id))
    return sort if sort in VALID_SORTS else "vol"


async def set_pairs_sort(user_id: int, sort_mode: str) -> str:
    if sort_mode not in VALID_SORTS:
        sort_mode = "vol"
    redis = await get_redis()
    await redis.set(PAIRS_SORT_KEY.format(user_id=user_id), sort_mode)
    return sort_mode
