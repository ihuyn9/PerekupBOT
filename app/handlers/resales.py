from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.item_actions import get_item_actions_keyboard, get_items_list_keyboard
from app.keyboards.main_menu import get_cancel_keyboard, get_main_menu, get_skip_keyboard
from app.keyboards.resales_menu import get_resales_menu
from app.services.bot_texts import get_text
from app.services.bot_users import is_admin_user
from app.services.expense_service import add_expense
from app.services.items import get_item, list_items
from app.services.resales import close_resale, create_resale
from app.states.resale_states import ResaleStates
from app.utils.calculations import parse_amount
from app.utils.constants import BUTTON_RESALES, ITEM_KIND_RESALE, SKIP_TEXT
from app.utils.formatters import format_item_card, format_items_overview


router = Router()


@router.message(F.text == BUTTON_RESALES)
async def open_resales_menu(message: Message) -> None:
    await message.answer(await get_text("resales_menu_text"), reply_markup=get_resales_menu())


@router.callback_query(F.data == "resales:create")
async def start_resale_creation(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ResaleStates.waiting_model)
    await callback.message.answer(
        "Введи модель устройства.\n\nПример: <code>Samsung S22</code>",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(ResaleStates.waiting_model)
async def process_resale_model(message: Message, state: FSMContext) -> None:
    model = (message.text or "").strip()
    if not model:
        await message.answer("Модель не должна быть пустой.")
        return

    await state.update_data(model=model)
    await state.set_state(ResaleStates.waiting_buy_price)
    await message.answer("Введи цену покупки.\n\nПример: <code>12000</code>")


@router.message(ResaleStates.waiting_buy_price)
async def process_resale_buy_price(message: Message, state: FSMContext) -> None:
    try:
        buy_price = parse_amount((message.text or "").strip(), allow_zero=True)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.update_data(buy_price=buy_price)
    await state.set_state(ResaleStates.waiting_note)
    await message.answer(
        "Можешь добавить комментарий: где купил, что с устройством и так далее. Или «Пропустить».",
        reply_markup=get_skip_keyboard(),
    )


@router.message(ResaleStates.waiting_note)
async def process_resale_note(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    note = None if raw_value == SKIP_TEXT else raw_value
    data = await state.get_data()

    item = await create_resale(
        owner_tg_id=message.from_user.id,
        model=data["model"],
        buy_price=data["buy_price"],
        note=note,
    )
    await state.clear()

    await message.answer(
        "Перепродажа создана.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    if item:
        await message.answer(
            format_item_card(item),
            reply_markup=get_item_actions_keyboard(item),
        )


@router.callback_query(F.data == "resales:active")
async def show_active_resales(callback: CallbackQuery) -> None:
    items = await list_items(
        owner_tg_id=callback.from_user.id,
        kind=ITEM_KIND_RESALE,
        active_only=True,
        limit=20,
    )
    await callback.message.answer(
        format_items_overview("Активные перепродажи", items),
        reply_markup=get_items_list_keyboard(items, "main:menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "resales:closed")
async def show_closed_resales(callback: CallbackQuery) -> None:
    items = await list_items(
        owner_tg_id=callback.from_user.id,
        kind=ITEM_KIND_RESALE,
        active_only=False,
        limit=20,
    )
    await callback.message.answer(
        format_items_overview("Закрытые перепродажи", items),
        reply_markup=get_items_list_keyboard(items, "main:menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "resales:archived")
async def show_archived_resales(callback: CallbackQuery) -> None:
    items = await list_items(
        owner_tg_id=callback.from_user.id,
        kind=ITEM_KIND_RESALE,
        archived_only=True,
        limit=20,
    )
    await callback.message.answer(
        format_items_overview("Архив перепродаж", items),
        reply_markup=get_items_list_keyboard(items, "main:menu"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("resale:expense:"))
async def start_resale_expense(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(item_id=item_id)
    await state.set_state(ResaleStates.waiting_expense_title)
    await callback.message.answer(
        "Напиши, какой был расход.\n\nПример: <code>Аккумулятор</code>",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(ResaleStates.waiting_expense_title)
async def process_resale_expense_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название расхода не должно быть пустым.")
        return

    await state.update_data(expense_title=title)
    await state.set_state(ResaleStates.waiting_expense_amount)
    await message.answer("Теперь введи сумму расхода.")


@router.message(ResaleStates.waiting_expense_amount)
async def process_resale_expense_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_amount((message.text or "").strip())
    except ValueError as exc:
        await message.answer(str(exc))
        return

    data = await state.get_data()
    await add_expense(
        owner_tg_id=message.from_user.id,
        item_id=data["item_id"],
        title=data["expense_title"],
        amount=amount,
    )
    item = await get_item(message.from_user.id, data["item_id"])
    await state.clear()

    await message.answer(
        "Расход добавлен.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    if item:
        await message.answer(
            format_item_card(item),
            reply_markup=get_item_actions_keyboard(item),
        )


@router.callback_query(F.data.startswith("resale:close:"))
async def start_resale_close(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(item_id=item_id)
    await state.set_state(ResaleStates.waiting_close_amount)
    await callback.message.answer(
        "Введи цену продажи.\n\nПример: <code>18500</code>",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(ResaleStates.waiting_close_amount)
async def process_resale_close(message: Message, state: FSMContext) -> None:
    try:
        sell_price = parse_amount((message.text or "").strip(), allow_zero=True)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    data = await state.get_data()
    item = await close_resale(message.from_user.id, data["item_id"], sell_price)
    await state.clear()

    await message.answer(
        "Перепродажа закрыта.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    if item:
        await message.answer(
            format_item_card(item),
            reply_markup=get_item_actions_keyboard(item),
        )
