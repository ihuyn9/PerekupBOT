from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_repairs_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новый ремонт", callback_data="repairs:create")],
            [InlineKeyboardButton(text="🧰 Активные ремонты", callback_data="repairs:active")],
            [InlineKeyboardButton(text="✅ Закрытые ремонты", callback_data="repairs:closed")],
            [InlineKeyboardButton(text="🗄 Архив ремонтов", callback_data="repairs:archived")],
        ]
    )
