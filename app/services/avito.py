from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from typing import Any

import aiohttp
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot import bot
from app.database.models import AvitoAccount, AvitoChat, AvitoMessage, Item
from app.database.session import async_session
from app.services.activity_logs import log_activity
from app.utils.constants import AVITO_CHAT_STAGE_DEAL, AVITO_CHAT_STAGE_NEW


API_BASE_URL = "https://api.avito.ru"
TOKEN_URL = f"{API_BASE_URL}/token"
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)


class AvitoApiError(Exception):
    pass


def parse_repair_ad_ids(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.utcnow()

    normalized = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.utcnow()


def _extract_chat_id(payload: dict[str, Any]) -> str:
    return str(payload.get("id") or payload.get("chat_id") or "")


def _extract_ad_info(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    context = payload.get("context") or {}
    context_value = context.get("value") or {}
    item = payload.get("item") or {}
    ad_id = context_value.get("id") or item.get("id") or payload.get("item_id")
    ad_title = context_value.get("title") or item.get("title") or payload.get("title")
    return (str(ad_id) if ad_id is not None else None, ad_title)


def _extract_chat_client_name(payload: dict[str, Any], avito_user_id: int | None) -> str | None:
    users = payload.get("users") or payload.get("participants") or []
    for user in users:
        user_id = str(user.get("id")) if user.get("id") is not None else None
        if avito_user_id is not None and user_id == str(avito_user_id):
            continue
        return user.get("name") or user.get("title") or user.get("username")
    return payload.get("client_name")


def _extract_message_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content") or {}
    text = (
        content.get("text")
        or content.get("message")
        or payload.get("text")
        or payload.get("message")
    )
    if text is None:
        return None
    return str(text)


def _extract_message_direction(payload: dict[str, Any], avito_user_id: int | None) -> str:
    author_id = payload.get("author_id") or payload.get("user_id")
    if avito_user_id is not None and author_id is not None and str(author_id) == str(avito_user_id):
        return "outgoing"
    return "incoming"


class AvitoApiClient:
    def __init__(self, account: AvitoAccount):
        self.account = account

    async def ensure_token(self) -> str:
        if (
            self.account.access_token
            and self.account.token_expires_at
            and self.account.token_expires_at > datetime.utcnow() + TOKEN_REFRESH_MARGIN
        ):
            return self.account.access_token

        return await self._refresh_token()

    async def _refresh_token(self) -> str:
        form_data = {
            "grant_type": "client_credentials",
            "client_id": self.account.client_id,
            "client_secret": self.account.client_secret,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(TOKEN_URL, data=form_data) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise AvitoApiError(payload.get("error_description") or payload.get("error") or "Avito token error")

        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 0)
        if not access_token:
            raise AvitoApiError("Avito не вернул access_token.")

        self.account.access_token = access_token
        self.account.token_expires_at = datetime.utcnow() + timedelta(seconds=max(expires_in - 60, 60))

        async with async_session() as session:
            stored_account = await session.get(AvitoAccount, self.account.id)
            if stored_account:
                stored_account.access_token = self.account.access_token
                stored_account.token_expires_at = self.account.token_expires_at
                await session.commit()

        return access_token

    async def _request(self, method: str, path: str, *, params: dict | None = None, json_data: dict | None = None) -> dict[str, Any]:
        token = await self.ensure_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.request(method, f"{API_BASE_URL}{path}", params=params, json=json_data) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise AvitoApiError(
                        payload.get("error", {}).get("message")
                        if isinstance(payload.get("error"), dict)
                        else payload.get("message") or str(payload)
                    )
                return payload

    async def fetch_self_user_id(self) -> int:
        payload = await self._request("GET", "/core/v1/accounts/self")
        avito_user_id = payload.get("id") or (payload.get("data") or {}).get("id")
        if avito_user_id is None:
            raise AvitoApiError("Не удалось определить user_id аккаунта Avito.")
        return int(avito_user_id)

    async def fetch_chats(self) -> list[dict[str, Any]]:
        if self.account.avito_user_id is None:
            self.account.avito_user_id = await self.fetch_self_user_id()

        payload = await self._request("GET", f"/messenger/v2/accounts/{self.account.avito_user_id}/chats")
        chats = payload.get("chats") or payload.get("items") or payload.get("result") or []
        if not isinstance(chats, list):
            return []
        return chats

    async def fetch_messages(self, avito_chat_id: str) -> list[dict[str, Any]]:
        if self.account.avito_user_id is None:
            self.account.avito_user_id = await self.fetch_self_user_id()

        payload = await self._request(
            "GET",
            f"/messenger/v1/accounts/{self.account.avito_user_id}/chats/{avito_chat_id}/messages/",
        )
        messages = payload.get("messages") or payload.get("items") or payload.get("result") or []
        if not isinstance(messages, list):
            return []
        return messages

    async def send_message(self, avito_chat_id: str, text: str) -> None:
        if self.account.avito_user_id is None:
            self.account.avito_user_id = await self.fetch_self_user_id()

        await self._request(
            "POST",
            f"/messenger/v1/accounts/{self.account.avito_user_id}/chats/{avito_chat_id}/messages",
            json_data={"message": {"text": text}},
        )


async def get_avito_account(owner_tg_id: int) -> AvitoAccount | None:
    async with async_session() as session:
        result = await session.execute(select(AvitoAccount).where(AvitoAccount.owner_tg_id == owner_tg_id))
        return result.scalar_one_or_none()


async def save_avito_account(
    *,
    owner_tg_id: int,
    client_id: str,
    client_secret: str,
) -> AvitoAccount:
    async with async_session() as session:
        result = await session.execute(select(AvitoAccount).where(AvitoAccount.owner_tg_id == owner_tg_id))
        account = result.scalar_one_or_none()

        if account is None:
            account = AvitoAccount(
                owner_tg_id=owner_tg_id,
                client_id=client_id,
                client_secret=client_secret,
            )
            session.add(account)
        else:
            account.client_id = client_id
            account.client_secret = client_secret
            account.avito_user_id = None
            account.access_token = None
            account.token_expires_at = None

        await session.commit()
        await session.refresh(account)
        return account


async def update_avito_repair_ads(owner_tg_id: int, repair_ad_ids: str) -> AvitoAccount | None:
    async with async_session() as session:
        result = await session.execute(select(AvitoAccount).where(AvitoAccount.owner_tg_id == owner_tg_id))
        account = result.scalar_one_or_none()
        if account is None:
            return None

        account.repair_ad_ids = repair_ad_ids
        await session.commit()
        await session.refresh(account)
        return account


async def set_avito_sync_enabled(owner_tg_id: int, enabled: bool) -> AvitoAccount | None:
    async with async_session() as session:
        result = await session.execute(select(AvitoAccount).where(AvitoAccount.owner_tg_id == owner_tg_id))
        account = result.scalar_one_or_none()
        if account is None:
            return None

        account.sync_enabled = enabled
        await session.commit()
        await session.refresh(account)
        return account


async def list_avito_chats(owner_tg_id: int) -> list[AvitoChat]:
    async with async_session() as session:
        result = await session.execute(
            select(AvitoChat)
            .options(selectinload(AvitoChat.linked_item))
            .where(AvitoChat.owner_tg_id == owner_tg_id)
            .order_by(AvitoChat.last_message_at.desc().nullslast(), AvitoChat.updated_at.desc())
        )
        return list(result.scalars().all())


async def get_avito_chat(owner_tg_id: int, chat_id: int) -> AvitoChat | None:
    async with async_session() as session:
        result = await session.execute(
            select(AvitoChat)
            .options(
                selectinload(AvitoChat.messages),
                selectinload(AvitoChat.account),
                selectinload(AvitoChat.linked_item),
            )
            .where(
                AvitoChat.id == chat_id,
                AvitoChat.owner_tg_id == owner_tg_id,
            )
        )
        return result.scalar_one_or_none()


async def mark_chat_read(owner_tg_id: int, chat_id: int) -> AvitoChat | None:
    async with async_session() as session:
        result = await session.execute(
            select(AvitoChat).where(
                AvitoChat.id == chat_id,
                AvitoChat.owner_tg_id == owner_tg_id,
            )
        )
        chat = result.scalar_one_or_none()
        if chat is None:
            return None

        chat.unread_count = 0
        await session.commit()

    return await get_avito_chat(owner_tg_id, chat_id)


async def _ensure_account_identity(account: AvitoAccount) -> AvitoAccount:
    client = AvitoApiClient(account)
    avito_user_id = await client.fetch_self_user_id()

    async with async_session() as session:
        stored = await session.get(AvitoAccount, account.id)
        if stored is None:
            raise AvitoApiError("Аккаунт Avito не найден.")

        stored.avito_user_id = avito_user_id
        stored.access_token = client.account.access_token
        stored.token_expires_at = client.account.token_expires_at
        await session.commit()
        await session.refresh(stored)
        return stored


async def sync_avito_account(owner_tg_id: int) -> dict[str, int]:
    account = await get_avito_account(owner_tg_id)
    if account is None:
        raise AvitoApiError("Сначала подключи Avito API в настройках.")

    if account.avito_user_id is None:
        account = await _ensure_account_identity(account)

    client = AvitoApiClient(account)
    chats_payload = await client.fetch_chats()
    allowed_ad_ids = set(parse_repair_ad_ids(account.repair_ad_ids))
    created_chats = 0
    new_messages = 0

    async with async_session() as session:
        stored_account = await session.get(AvitoAccount, account.id)
        if stored_account is None:
            raise AvitoApiError("Аккаунт Avito не найден.")

        for chat_payload in chats_payload:
            avito_chat_id = _extract_chat_id(chat_payload)
            if not avito_chat_id:
                continue

            ad_id, ad_title = _extract_ad_info(chat_payload)
            if allowed_ad_ids and (ad_id is None or ad_id not in allowed_ad_ids):
                continue

            result = await session.execute(
                select(AvitoChat).where(AvitoChat.avito_chat_id == avito_chat_id)
            )
            chat = result.scalar_one_or_none()
            is_new_chat = chat is None

            if chat is None:
                chat = AvitoChat(
                    account_id=stored_account.id,
                    owner_tg_id=stored_account.owner_tg_id,
                    avito_chat_id=avito_chat_id,
                    stage=AVITO_CHAT_STAGE_NEW,
                    unread_count=0,
                )
                session.add(chat)
                created_chats += 1

            chat.ad_id = ad_id
            chat.ad_title = ad_title
            chat.client_name = _extract_chat_client_name(chat_payload, stored_account.avito_user_id)
            chat.client_avito_id = str(chat_payload.get("user_id") or chat_payload.get("client_id") or "") or None
            chat.updated_at = datetime.utcnow()
            incoming_in_this_sync = 0

            messages_payload = await client.fetch_messages(avito_chat_id)
            latest_message_time = chat.last_message_at

            for message_payload in messages_payload:
                avito_message_id = str(message_payload.get("id") or message_payload.get("message_id") or "")
                if not avito_message_id:
                    continue

                existing_message = await session.execute(
                    select(AvitoMessage).where(AvitoMessage.avito_message_id == avito_message_id)
                )
                if existing_message.scalar_one_or_none() is not None:
                    continue

                direction = _extract_message_direction(message_payload, stored_account.avito_user_id)
                message_text = _extract_message_text(message_payload)
                created_at = _parse_datetime(
                    message_payload.get("created")
                    or message_payload.get("created_at")
                    or message_payload.get("timestamp")
                )
                author_name = message_payload.get("author_name") or message_payload.get("author") or chat.client_name

                session.add(
                    AvitoMessage(
                        chat=chat,
                        avito_message_id=avito_message_id,
                        direction=direction,
                        author_name=author_name,
                        text=message_text,
                        created_at=created_at,
                    )
                )
                new_messages += 1

                if direction == "incoming":
                    chat.unread_count += 1
                    incoming_in_this_sync += 1

                if latest_message_time is None or created_at > latest_message_time:
                    latest_message_time = created_at
                    chat.last_message_text = message_text

            chat.last_message_at = latest_message_time

            if is_new_chat or incoming_in_this_sync:
                title = escape(chat.ad_title or "объявление")
                name = escape(chat.client_name or "клиент Avito")
                await bot.send_message(
                    chat.owner_tg_id,
                    f"💬 <b>Новый диалог Avito</b>\n\nКлиент: {name}\nОбъявление: {title}",
                )

        stored_account.last_synced_at = datetime.utcnow()
        stored_account.access_token = client.account.access_token
        stored_account.token_expires_at = client.account.token_expires_at
        stored_account.avito_user_id = client.account.avito_user_id
        await session.commit()

    return {"created_chats": created_chats, "new_messages": new_messages}


async def sync_all_avito_accounts() -> None:
    async with async_session() as session:
        result = await session.execute(
            select(AvitoAccount).where(AvitoAccount.sync_enabled.is_(True))
        )
        accounts = list(result.scalars().all())

    for account in accounts:
        try:
            await sync_avito_account(account.owner_tg_id)
        except Exception:
            continue


async def send_avito_reply(owner_tg_id: int, chat_id: int, text: str) -> AvitoChat | None:
    chat = await get_avito_chat(owner_tg_id, chat_id)
    if chat is None or chat.account is None:
        return None

    client = AvitoApiClient(chat.account)
    await client.send_message(chat.avito_chat_id, text)

    async with async_session() as session:
        stored_chat = await session.get(AvitoChat, chat.id)
        if stored_chat is None:
            return None

        session.add(
            AvitoMessage(
                chat_id=stored_chat.id,
                avito_message_id=f"local-out-{datetime.utcnow().timestamp()}",
                direction="outgoing",
                author_name="Вы",
                text=text,
                created_at=datetime.utcnow(),
            )
        )
        stored_chat.last_message_text = text
        stored_chat.last_message_at = datetime.utcnow()
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="avito_chat",
        entity_id=chat_id,
        action="avito_reply_sent",
        summary=f"Отправлен ответ в Avito-чат #{chat_id}",
    )
    return await get_avito_chat(owner_tg_id, chat_id)


async def set_avito_chat_stage(owner_tg_id: int, chat_id: int, stage: str) -> AvitoChat | None:
    async with async_session() as session:
        result = await session.execute(
            select(AvitoChat).where(
                AvitoChat.id == chat_id,
                AvitoChat.owner_tg_id == owner_tg_id,
            )
        )
        chat = result.scalar_one_or_none()
        if chat is None:
            return None

        chat.stage = stage
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="avito_chat",
        entity_id=chat_id,
        action="avito_stage_updated",
        summary=f"Avito-чат #{chat_id}: этап изменен на {stage}",
    )
    return await get_avito_chat(owner_tg_id, chat_id)


async def link_chat_to_item(owner_tg_id: int, chat_id: int, item_id: int) -> AvitoChat | None:
    async with async_session() as session:
        chat_result = await session.execute(
            select(AvitoChat).where(
                AvitoChat.id == chat_id,
                AvitoChat.owner_tg_id == owner_tg_id,
            )
        )
        chat = chat_result.scalar_one_or_none()
        if chat is None:
            return None

        item_result = await session.execute(
            select(Item).where(
                Item.id == item_id,
                Item.owner_tg_id == owner_tg_id,
            )
        )
        item = item_result.scalar_one_or_none()
        if item is None:
            return None

        chat.linked_item_id = item.id
        chat.stage = AVITO_CHAT_STAGE_DEAL
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="avito_chat",
        entity_id=chat_id,
        action="avito_chat_linked",
        summary=f"Avito-чат #{chat_id} привязан к заказу #{item_id}",
    )
    return await get_avito_chat(owner_tg_id, chat_id)
