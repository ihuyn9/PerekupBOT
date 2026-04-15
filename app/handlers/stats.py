from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.services.bot_texts import get_text
from app.services.stats import get_month_stats
from app.states.common_states import CommonStates
from app.utils.constants import BUTTON_STATS


router = Router()


def get_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Текущий месяц", callback_data="stats:current"),
                InlineKeyboardButton(text="🕘 Прошлый месяц", callback_data="stats:last"),
            ],
            [InlineKeyboardButton(text="✍️ Ввести месяц", callback_data="stats:custom")],
        ]
    )


def shift_to_previous_month(today: datetime) -> tuple[int, int]:
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def parse_month_input(raw_value: str) -> tuple[int, int]:
    value = raw_value.strip().replace("/", ".").replace("-", ".")
    parts = value.split(".")

    if len(parts) != 2:
        raise ValueError("Используй формат MM.YYYY. Пример: 04.2026")

    month, year = int(parts[0]), int(parts[1])
    if month < 1 or month > 12:
        raise ValueError("Месяц должен быть от 1 до 12.")

    return year, month


@router.message(F.text == BUTTON_STATS)
async def open_stats_menu(message: Message) -> None:
    await message.answer(await get_text("stats_menu_text"), reply_markup=get_stats_keyboard())


@router.callback_query(F.data == "stats:current")
async def show_current_month_stats(callback: CallbackQuery) -> None:
    today = datetime.now()
    await callback.message.answer(await get_month_stats(callback.from_user.id, today.year, today.month))
    await callback.answer()


@router.callback_query(F.data == "stats:last")
async def show_last_month_stats(callback: CallbackQuery) -> None:
    year, month = shift_to_previous_month(datetime.now())
    await callback.message.answer(await get_month_stats(callback.from_user.id, year, month))
    await callback.answer()


@router.callback_query(F.data == "stats:custom")
async def request_custom_month(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CommonStates.waiting_stats_month)
    await callback.message.answer(
        "Введи месяц в формате MM.YYYY.\n\nПример: <code>04.2026</code>",
    )
    await callback.answer()


@router.message(CommonStates.waiting_stats_month)
async def process_custom_month(message: Message, state: FSMContext) -> None:
    try:
        year, month = parse_month_input(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.clear()
    await message.answer(await get_month_stats(message.from_user.id, year, month))
