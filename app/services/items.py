from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.config import get_config
from app.database.models import (
    ActivityLog,
    AvitoAccount,
    Client,
    Item,
    QuickReplyTemplate,
    RepairDetails,
)
from app.database.session import async_session
from app.services.activity_logs import log_activity
from app.utils.constants import (
    ITEM_KIND_REPAIR,
    PRIORITY_NORMAL,
    STAGE_BOUGHT,
    STAGE_NEW,
    STATUS_ACTIVE,
)
from app.utils.normalizers import normalize_person_name, normalize_phone, normalize_telegram_contact


config = get_config()

LOAD_OPTIONS = (
    selectinload(Item.repair_details).selectinload(RepairDetails.client),
    selectinload(Item.resale_details),
    selectinload(Item.expenses),
    selectinload(Item.avito_chats),
)


def apply_owner_scope(query, owner_tg_id: int):
    if config.admin_id is not None and owner_tg_id == config.admin_id:
        return query.where(or_(Item.owner_tg_id == owner_tg_id, Item.owner_tg_id.is_(None)))

    return query.where(Item.owner_tg_id == owner_tg_id)


def apply_visibility_scope(
    query,
    *,
    include_archived: bool = False,
    archived_only: bool = False,
    include_deleted: bool = False,
    deleted_only: bool = False,
):
    if deleted_only:
        query = query.where(Item.deleted_at.is_not(None))
    elif not include_deleted:
        query = query.where(Item.deleted_at.is_(None))

    if archived_only:
        query = query.where(Item.is_archived.is_(True))
    elif not include_archived:
        query = query.where(Item.is_archived.is_(False))

    return query


async def get_item(
    owner_tg_id: int,
    item_id: int,
    *,
    include_archived: bool = True,
    include_deleted: bool = True,
) -> Item | None:
    async with async_session() as session:
        query = apply_owner_scope(
            select(Item).options(*LOAD_OPTIONS).where(Item.id == item_id),
            owner_tg_id,
        )
        query = apply_visibility_scope(
            query,
            include_archived=include_archived,
            include_deleted=include_deleted,
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def list_items(
    *,
    owner_tg_id: int,
    kind: str | None = None,
    active_only: bool | None = None,
    limit: int = 20,
    archived_only: bool = False,
    include_archived: bool = False,
    include_deleted: bool = False,
) -> list[Item]:
    async with async_session() as session:
        query = apply_owner_scope(
            select(Item).options(*LOAD_OPTIONS).order_by(Item.created_at.desc()).limit(limit),
            owner_tg_id,
        )
        query = apply_visibility_scope(
            query,
            archived_only=archived_only,
            include_archived=include_archived,
            include_deleted=include_deleted,
        )

        if kind:
            query = query.where(Item.kind == kind)

        if active_only is True:
            query = query.where(Item.status == STATUS_ACTIVE)
        elif active_only is False:
            query = query.where(Item.status != STATUS_ACTIVE)

        result = await session.execute(query)
        return list(result.scalars().all())


async def search_items(
    owner_tg_id: int,
    query_text: str,
    limit: int = 20,
    *,
    include_archived: bool = True,
) -> list[Item]:
    query_text = query_text.strip()
    normalized_phone = normalize_phone(query_text)
    normalized_telegram = normalize_telegram_contact(query_text)

    async with async_session() as session:
        query = apply_owner_scope(
            select(Item)
            .distinct()
            .options(*LOAD_OPTIONS)
            .outerjoin(Item.repair_details)
            .outerjoin(RepairDetails.client)
            .order_by(Item.created_at.desc())
            .limit(limit),
            owner_tg_id,
        )
        query = apply_visibility_scope(query, include_archived=include_archived)

        conditions = [
            Item.model.ilike(f"%{query_text}%"),
            Client.full_name.ilike(f"%{query_text}%"),
        ]
        if normalized_phone:
            conditions.extend(
                [
                    Client.phone.ilike(f"%{query_text}%"),
                    Client.normalized_phone.ilike(f"%{normalized_phone}%"),
                ]
            )
        if normalized_telegram:
            conditions.extend(
                [
                    Client.telegram_contact.ilike(f"%{query_text}%"),
                    Client.normalized_telegram_contact.ilike(f"%{normalized_telegram}%"),
                ]
            )
        if query_text.isdigit():
            conditions.insert(0, Item.id == int(query_text))

        query = query.where(or_(*conditions))
        result = await session.execute(query)
        return list(result.scalars().all())


async def update_item_main_fields(
    owner_tg_id: int,
    item_id: int,
    *,
    model: str | None = None,
    note: str | None = None,
) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(select(Item).where(Item.id == item_id), owner_tg_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None

        changes: list[str] = []
        if model is not None:
            item.model = model.strip()
            changes.append(f"модель: {item.model}")
        if note is not None:
            item.note = note.strip() or None
            changes.append("комментарий обновлен")

        await session.commit()

    if changes:
        await log_activity(
            owner_tg_id=owner_tg_id,
            actor_tg_id=owner_tg_id,
            entity_type="item",
            entity_id=item_id,
            action="item_updated",
            summary=f"Заказ #{item_id}: " + ", ".join(changes),
        )

    return await get_item(owner_tg_id, item_id)


async def update_repair_client(
    owner_tg_id: int,
    item_id: int,
    *,
    client_name: str | None = None,
    phone: str | None = None,
    telegram_contact: str | None = None,
) -> Item | None:
    name_provided = client_name is not None
    phone_provided = phone is not None
    telegram_provided = telegram_contact is not None

    clean_name = " ".join((client_name or "").strip().split()) if name_provided else ""
    clean_phone = phone.strip() if phone_provided and phone else None
    clean_telegram = normalize_telegram_contact(telegram_contact) if telegram_provided else ""
    clean_telegram = clean_telegram or None
    normalized_phone = normalize_phone(clean_phone)
    normalized_telegram = normalize_telegram_contact(clean_telegram)

    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(
                select(Item)
                .options(selectinload(Item.repair_details).selectinload(RepairDetails.client))
                .where(Item.id == item_id),
                owner_tg_id,
            )
        )
        item = result.scalar_one_or_none()
        if item is None or item.kind != ITEM_KIND_REPAIR or item.repair_details is None:
            return None

        client = item.repair_details.client
        if client is None:
            lookup_conditions = []
            if clean_name:
                lookup_conditions.append(Client.normalized_name == normalize_person_name(clean_name))
            if normalized_phone:
                lookup_conditions.append(Client.normalized_phone == normalized_phone)
            if normalized_telegram:
                lookup_conditions.append(Client.normalized_telegram_contact == normalized_telegram)

            if lookup_conditions:
                client_result = await session.execute(
                    select(Client).where(
                        Client.owner_tg_id == owner_tg_id,
                        or_(*lookup_conditions),
                    )
                )
                client = client_result.scalar_one_or_none()

            if client is None and (clean_name or clean_phone or clean_telegram):
                display_name = clean_name or "Клиент без имени"
                client = Client(
                    owner_tg_id=owner_tg_id,
                    full_name=display_name,
                    normalized_name=normalize_person_name(display_name),
                    phone=clean_phone,
                    normalized_phone=normalized_phone or None,
                    telegram_contact=clean_telegram,
                    normalized_telegram_contact=normalized_telegram or None,
                )
                session.add(client)
                await session.flush()

            if client is not None:
                item.repair_details.client_id = client.id

        summary_parts: list[str] = []

        if client is not None:
            if name_provided:
                if clean_name:
                    client.full_name = clean_name
                    client.normalized_name = normalize_person_name(clean_name)
                    summary_parts.append(f"ФИО: {clean_name}")
                elif clean_phone or clean_telegram or client.phone or client.telegram_contact:
                    client.full_name = "Клиент без имени"
                    client.normalized_name = normalize_person_name(client.full_name)
                    summary_parts.append("ФИО очищено")

            if phone_provided:
                client.phone = clean_phone
                client.normalized_phone = normalized_phone or None
                summary_parts.append("телефон обновлен" if clean_phone else "телефон очищен")

            if telegram_provided:
                client.telegram_contact = clean_telegram
                client.normalized_telegram_contact = normalized_telegram or None
                summary_parts.append("Telegram обновлен" if clean_telegram else "Telegram очищен")

            if client.full_name == "Клиент без имени" and not client.phone and not client.telegram_contact:
                await session.delete(client)
                item.repair_details.client_id = None
                item.repair_details.client_name = None
                summary_parts.append("данные клиента очищены")
            else:
                item.repair_details.client_id = client.id
                item.repair_details.client_name = client.full_name
        elif any(value is not None for value in (client_name, phone, telegram_contact)):
            item.repair_details.client_id = None
            item.repair_details.client_name = None
            summary_parts.append("данные клиента очищены")

        await session.commit()

    if summary_parts:
        await log_activity(
            owner_tg_id=owner_tg_id,
            actor_tg_id=owner_tg_id,
            entity_type="item",
            entity_id=item_id,
            action="repair_client_updated",
            summary=f"Заказ #{item_id}: " + ", ".join(summary_parts),
        )
    return await get_item(owner_tg_id, item_id)


async def update_repair_amounts(
    owner_tg_id: int,
    item_id: int,
    *,
    prepayment=None,
    final_received=None,
) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(
                select(Item).options(selectinload(Item.repair_details)).where(Item.id == item_id),
                owner_tg_id,
            )
        )
        item = result.scalar_one_or_none()
        if item is None or item.kind != ITEM_KIND_REPAIR or item.repair_details is None:
            return None

        changes: list[str] = []
        if prepayment is not None:
            item.repair_details.prepayment_amount = prepayment
            changes.append("предоплата обновлена")
        if final_received is not None:
            item.repair_details.final_received_amount = final_received
            changes.append("сумма при выдаче обновлена")

        await session.commit()

    if changes:
        await log_activity(
            owner_tg_id=owner_tg_id,
            actor_tg_id=owner_tg_id,
            entity_type="item",
            entity_id=item_id,
            action="repair_amounts_updated",
            summary=f"Заказ #{item_id}: " + ", ".join(changes),
        )
    return await get_item(owner_tg_id, item_id)


async def update_resale_prices(
    owner_tg_id: int,
    item_id: int,
    *,
    buy_price=None,
    sell_price=None,
) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(
                select(Item).options(selectinload(Item.resale_details)).where(Item.id == item_id),
                owner_tg_id,
            )
        )
        item = result.scalar_one_or_none()
        if item is None or item.resale_details is None:
            return None

        changes: list[str] = []
        if buy_price is not None:
            item.resale_details.buy_price = buy_price
            changes.append("цена покупки обновлена")
        if sell_price is not None:
            item.resale_details.sell_price = sell_price
            changes.append("цена продажи обновлена")

        await session.commit()

    if changes:
        await log_activity(
            owner_tg_id=owner_tg_id,
            actor_tg_id=owner_tg_id,
            entity_type="item",
            entity_id=item_id,
            action="resale_prices_updated",
            summary=f"Заказ #{item_id}: " + ", ".join(changes),
        )
    return await get_item(owner_tg_id, item_id)


async def set_item_stage(owner_tg_id: int, item_id: int, stage: str) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(select(Item).where(Item.id == item_id), owner_tg_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None

        item.stage = stage
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="item_stage_updated",
        summary=f"Заказ #{item_id}: этап изменен на {stage}",
    )
    return await get_item(owner_tg_id, item_id)


async def set_item_priority(owner_tg_id: int, item_id: int, priority: str) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(select(Item).where(Item.id == item_id), owner_tg_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None

        item.priority = priority
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="item_priority_updated",
        summary=f"Заказ #{item_id}: приоритет изменен на {priority}",
    )
    return await get_item(owner_tg_id, item_id)


async def set_item_reminder(owner_tg_id: int, item_id: int, reminder_at) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(select(Item).where(Item.id == item_id), owner_tg_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None

        item.reminder_at = reminder_at
        item.reminder_sent_at = None
        await session.commit()

    summary = (
        f"Заказ #{item_id}: напоминание установлено на {reminder_at.strftime('%d.%m.%Y %H:%M')}"
        if reminder_at
        else f"Заказ #{item_id}: напоминание очищено"
    )
    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="item_reminder_updated",
        summary=summary,
    )
    return await get_item(owner_tg_id, item_id)


async def archive_item(owner_tg_id: int, item_id: int) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(select(Item).where(Item.id == item_id), owner_tg_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None

        item.is_archived = True
        item.archived_at = datetime.utcnow()
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="item_archived",
        summary=f"Заказ #{item_id} отправлен в архив",
    )
    return await get_item(owner_tg_id, item_id)


async def restore_item(owner_tg_id: int, item_id: int) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(select(Item).where(Item.id == item_id), owner_tg_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None

        item.is_archived = False
        item.archived_at = None
        item.deleted_at = None
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="item_restored",
        summary=f"Заказ #{item_id} восстановлен",
    )
    return await get_item(owner_tg_id, item_id)


async def soft_delete_item(owner_tg_id: int, item_id: int) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(select(Item).where(Item.id == item_id), owner_tg_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None

        item.deleted_at = datetime.utcnow()
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="item_deleted",
        summary=f"Заказ #{item_id} помечен как удаленный",
    )
    return await get_item(owner_tg_id, item_id)


async def hard_delete_item(owner_tg_id: int, item_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            apply_owner_scope(select(Item).where(Item.id == item_id), owner_tg_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return False

        await session.delete(item)
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="item",
        entity_id=item_id,
        action="item_hard_deleted",
        summary=f"Заказ #{item_id} удален навсегда",
    )
    return True


async def reset_user_data(owner_tg_id: int) -> None:
    async with async_session() as session:
        activity_logs = await session.execute(
            select(ActivityLog).where(ActivityLog.owner_tg_id == owner_tg_id)
        )
        for row in activity_logs.scalars().all():
            await session.delete(row)

        templates = await session.execute(
            select(QuickReplyTemplate).where(QuickReplyTemplate.owner_tg_id == owner_tg_id)
        )
        for row in templates.scalars().all():
            await session.delete(row)

        clients = await session.execute(select(Client).where(Client.owner_tg_id == owner_tg_id))
        for row in clients.scalars().all():
            await session.delete(row)

        accounts = await session.execute(
            select(AvitoAccount).where(AvitoAccount.owner_tg_id == owner_tg_id)
        )
        for row in accounts.scalars().all():
            await session.delete(row)

        items = await session.execute(select(Item).where(Item.owner_tg_id == owner_tg_id))
        for row in items.scalars().all():
            await session.delete(row)

        await session.commit()


def get_default_stage(kind: str) -> str:
    return STAGE_NEW if kind == ITEM_KIND_REPAIR else STAGE_BOUGHT


def get_default_priority() -> str:
    return PRIORITY_NORMAL
