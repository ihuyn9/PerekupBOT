from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.utils.constants import (
    BUTTON_ACTIVE,
    BUTTON_ADMIN,
    BUTTON_AVITO_CHATS,
    BUTTON_MENU,
    BUTTON_REPAIRS,
    BUTTON_RESALES,
    BUTTON_SEARCH,
    BUTTON_SETTINGS,
    BUTTON_STATS,
    CANCEL_TEXT,
    SKIP_TEXT,
)


def get_main_menu(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=BUTTON_REPAIRS), KeyboardButton(text=BUTTON_RESALES)],
        [KeyboardButton(text=BUTTON_ACTIVE), KeyboardButton(text=BUTTON_STATS)],
        [KeyboardButton(text=BUTTON_AVITO_CHATS), KeyboardButton(text=BUTTON_SEARCH)],
        [KeyboardButton(text=BUTTON_SETTINGS), KeyboardButton(text=BUTTON_MENU)],
    ]

    if is_admin:
        keyboard.append([KeyboardButton(text=BUTTON_ADMIN)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выбери раздел ниже",
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
        input_field_placeholder="Можно отменить действие",
    )


def get_skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SKIP_TEXT)], [KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
        input_field_placeholder="Можно пропустить этот шаг",
    )
