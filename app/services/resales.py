from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.database.models import Item, ResaleDetails
from app.database.session import async_session
from app.services.activity_logs import log_activity
from app.services.items import get_default_priority, get_default_stage, get_item
from app.utils.constants import ITEM_KIND_RESALE, STAGE_COMPLETED, STATUS_ACTIVE, STATUS_SOLD


async def create_resale(
    *,
    owner_tg_id: int,
    model: str,
    buy_price: Decimal,
    note: str | None = None,
) -> Item | None:
    async with async_session() as session:
        item = Item(
            owner_tg_id=owner_tg_id,
            kind=ITEM_KIND_RESALE,
            model=model,
            status=STATUS_ACTIVE,
            stage=get_default_stage(ITEM_KIND_RESALE),
            priority=get_default_priority(),
            note=note,
        )
        session.add(item)
        await session.flush()

        details = ResaleDetails(
            item_id=item.id,
            buy_price=buy_price,
            sell_price=Decimal("0"),
        )
        session.add(details)
        await session.commit()
        item_id = item.id

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="resale_created",
        summary=f"Создана перепродажа #{item_id} для {model}",
    )
    return await get_item(owner_tg_id, item_id)


async def close_resale(owner_tg_id: int, item_id: int, sell_price: Decimal) -> Item | None:
    async with async_session() as session:
        item = await session.get(Item, item_id)
        if (
            not item
            or item.owner_tg_id != owner_tg_id
            or item.kind != ITEM_KIND_RESALE
            or item.status != STATUS_ACTIVE
        ):
            return None

        result = await session.execute(select(ResaleDetails).where(ResaleDetails.item_id == item_id))
        details = result.scalar_one_or_none()

        if details is None:
            details = ResaleDetails(
                item_id=item_id,
                buy_price=Decimal("0"),
                sell_price=Decimal("0"),
            )
            session.add(details)
            await session.flush()

        details.sell_price = sell_price
        item.status = STATUS_SOLD
        item.stage = STAGE_COMPLETED
        item.closed_at = datetime.utcnow()
        item.reminder_at = None
        item.reminder_sent_at = None
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="resale_closed",
        summary=f"Перепродажа #{item_id} закрыта, цена продажи {sell_price}",
    )
    return await get_item(owner_tg_id, item_id)
