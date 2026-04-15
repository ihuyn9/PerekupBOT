from datetime import datetime

from sqlalchemy import select

from app.database.models import Item, RepairDetails
from app.database.session import async_session
from app.services.items import LOAD_OPTIONS, apply_owner_scope
from app.utils.constants import STATUS_ACTIVE


async def get_due_reminders(limit: int = 50) -> list[Item]:
    async with async_session() as session:
        result = await session.execute(
            select(Item)
            .options(*LOAD_OPTIONS)
            .where(
                Item.status == STATUS_ACTIVE,
                Item.deleted_at.is_(None),
                Item.is_archived.is_(False),
                Item.reminder_at.is_not(None),
                Item.reminder_at <= datetime.utcnow(),
                Item.reminder_sent_at.is_(None),
            )
            .order_by(Item.reminder_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def mark_reminder_sent(item_id: int) -> None:
    async with async_session() as session:
        item = await session.get(Item, item_id)
        if item is None:
            return

        item.reminder_sent_at = datetime.utcnow()
        await session.commit()
