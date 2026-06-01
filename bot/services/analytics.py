from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserEvent


async def track(
    session: AsyncSession,
    user_id: int,
    event: str,
    **metadata: Any,
) -> None:
    session.add(
        UserEvent(
            user_id=user_id,
            event=event,
            event_metadata=metadata or None,
        )
    )
