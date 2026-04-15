from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import AvitoChat, QuickReplyTemplate
from app.utils.constants import (
    AVITO_CHAT_STAGE_CLOSED,
    AVITO_CHAT_STAGE_DEAL,
    AVITO_CHAT_STAGE_IN_PROGRESS,
    AVITO_CHAT_STAGE_NEW,
)


def get_avito_chats_keyboard(chats: list[AvitoChat]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for chat in chats:
        unread = f" [{chat.unread_count}]" if chat.unread_count else ""
        title = chat.ad_title or "Объявление"
        name = chat.client_name or "Клиент Avito"
        linked = f" • #{chat.linked_item_id}" if chat.linked_item_id else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"💬 {name} • {title}{unread}{linked}",
                    callback_data=f"avito:chat:{chat.id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="avito:refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_avito_chat_actions_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✉️ Ответить", callback_data=f"avito:reply:{chat_id}")],
            [InlineKeyboardButton(text="⚡ Шаблоны", callback_data=f"avito:templates:{chat_id}")],
            [InlineKeyboardButton(text="🧭 Этап лида", callback_data=f"avito:stage:{chat_id}")],
            [InlineKeyboardButton(text="🛠 Создать ремонт", callback_data=f"avito:create_repair:{chat_id}")],
            [InlineKeyboardButton(text="💸 Создать перепродажу", callback_data=f"avito:create_resale:{chat_id}")],
            [InlineKeyboardButton(text="🔄 Обновить чат", callback_data=f"avito:chat_refresh:{chat_id}")],
            [InlineKeyboardButton(text="⬅️ К чатам", callback_data="avito:list")],
        ]
    )


def get_avito_templates_keyboard(chat_id: int, templates: list[QuickReplyTemplate]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=f"⚡ {template.title}", callback_data=f"avito:template_send:{chat_id}:{template.id}")]
        for template in templates
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад к чату", callback_data=f"avito:chat:{chat_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_avito_stage_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🆕 Новый лид", callback_data=f"avito:set_stage:{chat_id}:{AVITO_CHAT_STAGE_NEW}")],
        [InlineKeyboardButton(text="💬 В работе", callback_data=f"avito:set_stage:{chat_id}:{AVITO_CHAT_STAGE_IN_PROGRESS}")],
        [InlineKeyboardButton(text="🤝 Договорились", callback_data=f"avito:set_stage:{chat_id}:{AVITO_CHAT_STAGE_DEAL}")],
        [InlineKeyboardButton(text="✅ Закрыт", callback_data=f"avito:set_stage:{chat_id}:{AVITO_CHAT_STAGE_CLOSED}")],
        [InlineKeyboardButton(text="⬅️ Назад к чату", callback_data=f"avito:chat:{chat_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
