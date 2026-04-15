from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.item_actions import get_item_actions_keyboard, get_items_list_keyboard
from app.keyboards.main_menu import get_cancel_keyboard, get_main_menu, get_skip_keyboard
from app.keyboards.repairs_menu import get_repairs_menu
from app.services.bot_texts import get_text
from app.services.bot_users import is_admin_user
from app.services.expense_service import add_expense
from app.services.items import get_item, list_items
from app.services.repairs import add_prepayment, close_repair, create_repair
from app.states.repair_states import RepairStates
from app.utils.calculations import parse_amount
from app.utils.constants import BUTTON_REPAIRS, ITEM_KIND_REPAIR, SKIP_TEXT
from app.utils.formatters import format_item_card, format_items_overview


router = Router()


@router.message(F.text == BUTTON_REPAIRS)
async def open_repairs_menu(message: Message) -> None:
    await message.answer(await get_text("repairs_menu_text"), reply_markup=get_repairs_menu())


@router.callback_query(F.data == "repairs:create")
async def start_repair_creation(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RepairStates.waiting_model)
    await callback.message.answer(
        "Введи модель устройства.\n\nПример: <code>iPhone 11</code>",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(RepairStates.waiting_model)
async def process_repair_model(message: Message, state: FSMContext) -> None:
    model = (message.text or "").strip()
    if not model:
        await message.answer("Модель не должна быть пустой.")
        return

    await state.update_data(model=model)
    await state.set_state(RepairStates.waiting_client_name)
    await message.answer(
        "Если это клиентский ремонт, введи имя клиента. Если не нужно, нажми «Пропустить».",
        reply_markup=get_skip_keyboard(),
    )


@router.message(RepairStates.waiting_client_name)
async def process_repair_client_name(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    client_name = None if raw_value == SKIP_TEXT else raw_value

    await state.update_data(client_name=client_name)
    await state.set_state(RepairStates.waiting_client_phone)
    await message.answer(
        "Если хочешь, добавь номер клиента. Или нажми «Пропустить».",
        reply_markup=get_skip_keyboard(),
    )


@router.message(RepairStates.waiting_client_phone)
async def process_repair_client_phone(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    client_phone = None if raw_value == SKIP_TEXT else raw_value

    await state.update_data(client_phone=client_phone)
    await state.set_state(RepairStates.waiting_client_telegram)
    await message.answer(
        "Если хочешь, добавь Telegram клиента: @username или ссылку. Или «Пропустить».",
        reply_markup=get_skip_keyboard(),
    )


@router.message(RepairStates.waiting_client_telegram)
async def process_repair_client_telegram(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    client_telegram = None if raw_value == SKIP_TEXT else raw_value

    await state.update_data(client_telegram=client_telegram)
    await state.set_state(RepairStates.waiting_note)
    await message.answer(
        "Можешь добавить комментарий: неисправность, договоренности, что угодно. Или «Пропустить».",
        reply_markup=get_skip_keyboard(),
    )


@router.message(RepairStates.waiting_note)
async def process_repair_note(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    note = None if raw_value == SKIP_TEXT else raw_value

    data = await state.get_data()
    item = await create_repair(
        owner_tg_id=message.from_user.id,
        model=data["model"],
        client_name=data.get("client_name"),
        client_phone=data.get("client_phone"),
        client_telegram_contact=data.get("client_telegram"),
        note=note,
    )
    await state.clear()

    await message.answer(
        "Ремонт создан.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    if item:
        await message.answer(
            format_item_card(item),
            reply_markup=get_item_actions_keyboard(item),
        )


@router.callback_query(F.data == "repairs:active")
async def show_active_repairs(callback: CallbackQuery) -> None:
    items = await list_items(
        owner_tg_id=callback.from_user.id,
        kind=ITEM_KIND_REPAIR,
        active_only=True,
        limit=20,
    )
    await callback.message.answer(
        format_items_overview("Активные ремонты", items),
        reply_markup=get_items_list_keyboard(items, "main:menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "repairs:closed")
async def show_closed_repairs(callback: CallbackQuery) -> None:
    items = await list_items(
        owner_tg_id=callback.from_user.id,
        kind=ITEM_KIND_REPAIR,
        active_only=False,
        limit=20,
    )
    await callback.message.answer(
        format_items_overview("Закрытые ремонты", items),
        reply_markup=get_items_list_keyboard(items, "main:menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "repairs:archived")
async def show_archived_repairs(callback: CallbackQuery) -> None:
    items = await list_items(
        owner_tg_id=callback.from_user.id,
        kind=ITEM_KIND_REPAIR,
        archived_only=True,
        limit=20,
    )
    await callback.message.answer(
        format_items_overview("Архив ремонтов", items),
        reply_markup=get_items_list_keyboard(items, "main:menu"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("repair:expense:"))
async def start_repair_expense(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(item_id=item_id)
    await state.set_state(RepairStates.waiting_expense_title)
    await callback.message.answer(
        "Напиши, на что был расход.\n\nПример: <code>Дисплей</code>",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(RepairStates.waiting_expense_title)
async def process_repair_expense_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название расхода не должно быть пустым.")
        return

    await state.update_data(expense_title=title)
    await state.set_state(RepairStates.waiting_expense_amount)
    await message.answer("Теперь введи сумму расхода.\n\nПример: <code>3500</code>")


@router.message(RepairStates.waiting_expense_amount)
async def process_repair_expense_amount(message: Message, state: FSMContext) -> None:
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


@router.callback_query(F.data.startswith("repair:prepayment:"))
async def start_prepayment(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(item_id=item_id)
    await state.set_state(RepairStates.waiting_prepayment_amount)
    await callback.message.answer(
        "Введи сумму предоплаты.\n\nПример: <code>2000</code>",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(RepairStates.waiting_prepayment_amount)
async def process_prepayment(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_amount((message.text or "").strip())
    except ValueError as exc:
        await message.answer(str(exc))
        return

    data = await state.get_data()
    item = await add_prepayment(message.from_user.id, data["item_id"], amount)
    await state.clear()

    await message.answer(
        "Предоплата добавлена.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    if item:
        await message.answer(
            format_item_card(item),
            reply_markup=get_item_actions_keyboard(item),
        )


@router.callback_query(F.data.startswith("repair:close:"))
async def start_repair_close(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(item_id=item_id)
    await state.set_state(RepairStates.waiting_close_amount)
    await callback.message.answer(
        "Сколько получаешь на руки при выдаче сейчас?\n\n"
        "Если была предоплата, введи только остаток, который получил при выдаче.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(RepairStates.waiting_close_amount)
async def process_repair_close(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_amount((message.text or "").strip(), allow_zero=True)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    data = await state.get_data()
    item = await close_repair(message.from_user.id, data["item_id"], amount)
    await state.clear()

    await message.answer(
        "Ремонт закрыт.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    if item:
        await message.answer(
            format_item_card(item),
            reply_markup=get_item_actions_keyboard(item),
        )
