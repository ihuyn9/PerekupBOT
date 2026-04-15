from sqlalchemy import or_, select

from app.database.models import Client, Item, RepairDetails
from app.database.session import async_session
from app.services.items import LOAD_OPTIONS, apply_owner_scope
from app.utils.normalizers import normalize_person_name, normalize_phone, normalize_telegram_contact


async def get_or_create_client(
    owner_tg_id: int,
    full_name: str,
    *,
    phone: str | None = None,
    telegram_contact: str | None = None,
) -> Client:
    normalized_name = normalize_person_name(full_name)
    normalized_phone = normalize_phone(phone)
    normalized_telegram_contact = normalize_telegram_contact(telegram_contact)
    clean_name = " ".join(full_name.strip().split())
    clean_phone = phone.strip() if phone else None
    clean_telegram_contact = normalize_telegram_contact(telegram_contact) or None

    async with async_session() as session:
        conditions = [
            Client.owner_tg_id == owner_tg_id,
            Client.normalized_name == normalized_name,
        ]
        if normalized_phone:
            conditions.append(Client.normalized_phone == normalized_phone)
        elif normalized_telegram_contact:
            conditions.append(Client.normalized_telegram_contact == normalized_telegram_contact)

        result = await session.execute(select(Client).where(*conditions))
        client = result.scalar_one_or_none()

        if client is None:
            if normalized_phone or normalized_telegram_contact:
                fallback_conditions = []
                if normalized_phone:
                    fallback_conditions.append(Client.normalized_phone == normalized_phone)
                if normalized_telegram_contact:
                    fallback_conditions.append(
                        Client.normalized_telegram_contact == normalized_telegram_contact
                    )
                fallback_result = await session.execute(
                    select(Client).where(
                        Client.owner_tg_id == owner_tg_id,
                        or_(*fallback_conditions),
                    )
                )
                client = fallback_result.scalar_one_or_none()

        if client is None:
            client = Client(
                owner_tg_id=owner_tg_id,
                full_name=clean_name,
                normalized_name=normalized_name,
                phone=clean_phone,
                normalized_phone=normalized_phone or None,
                telegram_contact=clean_telegram_contact,
                normalized_telegram_contact=normalized_telegram_contact or None,
            )
            session.add(client)
        else:
            client.full_name = clean_name
            client.normalized_name = normalized_name
            if clean_phone:
                client.phone = clean_phone
                client.normalized_phone = normalized_phone or None
            if clean_telegram_contact:
                client.telegram_contact = clean_telegram_contact
                client.normalized_telegram_contact = normalized_telegram_contact or None

        await session.commit()
        await session.refresh(client)
        return client


async def get_client(owner_tg_id: int, client_id: int) -> Client | None:
    async with async_session() as session:
        result = await session.execute(
            select(Client).where(
                Client.id == client_id,
                Client.owner_tg_id == owner_tg_id,
            )
        )
        return result.scalar_one_or_none()


async def get_client_history(owner_tg_id: int, client_id: int) -> tuple[Client | None, list[Item]]:
    async with async_session() as session:
        client_result = await session.execute(
            select(Client).where(
                Client.id == client_id,
                Client.owner_tg_id == owner_tg_id,
            )
        )
        client = client_result.scalar_one_or_none()
        if client is None:
            return None, []

        items_result = await session.execute(
            apply_owner_scope(
                select(Item)
                .options(*LOAD_OPTIONS)
                .join(Item.repair_details)
                .where(RepairDetails.client_id == client_id)
                .order_by(Item.created_at.desc()),
                owner_tg_id,
            )
        )
        return client, list(items_result.scalars().all())
