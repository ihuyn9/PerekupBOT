from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.database.models import Item, RepairDetails
from app.database.session import async_session
from app.services.activity_logs import log_activity
from app.services.clients import get_or_create_client
from app.services.items import get_default_priority, get_default_stage, get_item
from app.utils.constants import ITEM_KIND_REPAIR, STAGE_COMPLETED, STATUS_ACTIVE, STATUS_ISSUED


async def create_repair(
    *,
    owner_tg_id: int,
    model: str,
    client_name: str | None = None,
    client_phone: str | None = None,
    client_telegram_contact: str | None = None,
    note: str | None = None,
) -> Item | None:
    client_id: int | None = None
    clean_client_name: str | None = None

    if client_name or client_phone or client_telegram_contact:
        client = await get_or_create_client(
            owner_tg_id,
            client_name or "Клиент без имени",
            phone=client_phone,
            telegram_contact=client_telegram_contact,
        )
        client_id = client.id
        clean_client_name = client.full_name

    async with async_session() as session:
        item = Item(
            owner_tg_id=owner_tg_id,
            kind=ITEM_KIND_REPAIR,
            model=model,
            status=STATUS_ACTIVE,
            stage=get_default_stage(ITEM_KIND_REPAIR),
            priority=get_default_priority(),
            note=note,
        )
        session.add(item)
        await session.flush()

        details = RepairDetails(
            item_id=item.id,
            client_id=client_id,
            client_name=clean_client_name,
            prepayment_amount=Decimal("0"),
            final_received_amount=Decimal("0"),
        )
        session.add(details)
        await session.commit()
        item_id = item.id

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="repair_created",
        summary=f"Создан ремонт #{item_id} для {model}",
    )
    return await get_item(owner_tg_id, item_id)


async def add_prepayment(owner_tg_id: int, item_id: int, amount: Decimal) -> Item | None:
    async with async_session() as session:
        item = await session.get(Item, item_id)
        if (
            not item
            or item.owner_tg_id != owner_tg_id
            or item.kind != ITEM_KIND_REPAIR
            or item.status != STATUS_ACTIVE
        ):
            return None

        result = await session.execute(select(RepairDetails).where(RepairDetails.item_id == item_id))
        details = result.scalar_one_or_none()

        if details is None:
            details = RepairDetails(
                item_id=item_id,
                prepayment_amount=Decimal("0"),
                final_received_amount=Decimal("0"),
            )
            session.add(details)
            await session.flush()

        details.prepayment_amount += amount
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="repair_prepayment_added",
        summary=f"В ремонт #{item_id} добавлена предоплата {amount}",
    )
    return await get_item(owner_tg_id, item_id)


async def close_repair(owner_tg_id: int, item_id: int, final_received_amount: Decimal) -> Item | None:
    async with async_session() as session:
        item = await session.get(Item, item_id)
        if (
            not item
            or item.owner_tg_id != owner_tg_id
            or item.kind != ITEM_KIND_REPAIR
            or item.status != STATUS_ACTIVE
        ):
            return None

        result = await session.execute(select(RepairDetails).where(RepairDetails.item_id == item_id))
        details = result.scalar_one_or_none()

        if details is None:
            details = RepairDetails(
                item_id=item_id,
                prepayment_amount=Decimal("0"),
                final_received_amount=Decimal("0"),
            )
            session.add(details)
            await session.flush()

        details.final_received_amount = final_received_amount
        item.status = STATUS_ISSUED
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
        action="repair_closed",
        summary=f"Ремонт #{item_id} закрыт, получено при выдаче {final_received_amount}",
    )
    return await get_item(owner_tg_id, item_id)
