from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import BotUser
from app.utils.texts import BOT_TEXT_TITLES, DEFAULT_BOT_TEXTS


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users")],
            [InlineKeyboardButton(text="🔕 Выключили рассылку", callback_data="admin:broadcast_off")],
            [InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="📋 Активность", callback_data="admin:activity")],
            [InlineKeyboardButton(text="✏️ Тексты бота", callback_data="admin:texts")],
            [InlineKeyboardButton(text="⬇️ Обновить из GitHub", callback_data="admin:update")],
            [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="admin:restart")],
            [InlineKeyboardButton(text="🛑 Остановить бота", callback_data="admin:stop")],
        ]
    )


def get_admin_users_keyboard(users: list[BotUser]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for user in users:
        status = "забанен" if user.is_banned else "активен"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"👤 {user.full_name} ({status})",
                    callback_data=f"admin:user:{user.tg_id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_admin_user_actions_keyboard(user: BotUser) -> InlineKeyboardMarkup:
    ban_text = "✅ Разбанить" if user.is_banned else "⛔ Забанить"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=ban_text, callback_data=f"admin:ban:{user.tg_id}")],
            [InlineKeyboardButton(text="👥 К списку пользователей", callback_data="admin:users")],
            [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin:panel")],
        ]
    )


def get_admin_texts_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=BOT_TEXT_TITLES[key],
                callback_data=f"admin:text:{key}",
            )
        ]
        for key in DEFAULT_BOT_TEXTS
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
