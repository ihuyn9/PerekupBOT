from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_resales_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новая перепродажа", callback_data="resales:create")],
            [InlineKeyboardButton(text="📦 Активные перепродажи", callback_data="resales:active")],
            [InlineKeyboardButton(text="✅ Закрытые перепродажи", callback_data="resales:closed")],
            [InlineKeyboardButton(text="🗄 Архив перепродаж", callback_data="resales:archived")],
        ]
    )
