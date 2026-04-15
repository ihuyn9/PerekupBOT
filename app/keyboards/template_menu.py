from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import QuickReplyTemplate


def get_templates_management_keyboard(templates: list[QuickReplyTemplate]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for template in templates:
        rows.append(
            [
                InlineKeyboardButton(text=f"✏️ {template.title}", callback_data=f"settings:template_edit:{template.id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"settings:template_delete:{template.id}"),
            ]
        )

    rows.append([InlineKeyboardButton(text="➕ Новый шаблон", callback_data="settings:template_new")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад к настройкам", callback_data="settings:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
