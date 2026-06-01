import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

DEFAULT_CONCURRENCY = 10


async def run_batched(
    items: list[T],
    worker: Callable[[T], Awaitable[None]],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> None:
    sem = asyncio.Semaphore(concurrency)

    async def _wrap(item: T) -> None:
        async with sem:
            await worker(item)

    await asyncio.gather(*[_wrap(item) for item in items])
