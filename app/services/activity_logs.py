from sqlalchemy import select

from app.database.models import ActivityLog
from app.database.session import async_session


async def log_activity(
    *,
    owner_tg_id: int,
    actor_tg_id: int,
    entity_type: str,
    action: str,
    summary: str,
    entity_id: int | None = None,
) -> ActivityLog:
    async with async_session() as session:
        log = ActivityLog(
            owner_tg_id=owner_tg_id,
            actor_tg_id=actor_tg_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            summary=summary,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


async def list_recent_activity(*, owner_tg_id: int | None = None, limit: int = 30) -> list[ActivityLog]:
    async with async_session() as session:
        query = select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
        if owner_tg_id is not None:
            query = query.where(ActivityLog.owner_tg_id == owner_tg_id)

        result = await session.execute(query)
        return list(result.scalars().all())
