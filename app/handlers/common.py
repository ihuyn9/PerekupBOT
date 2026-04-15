from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.item_actions import (
    get_expenses_list_keyboard,
    get_item_actions_keyboard,
    get_item_edit_keyboard,
    get_item_priority_keyboard,
    get_item_reminder_keyboard,
    get_item_stage_keyboard,
    get_items_list_keyboard,
)
from app.keyboards.main_menu import get_main_menu
from app.services.bot_users import is_admin_user
from app.services.clients import get_client_history
from app.services.expense_service import delete_expense
from app.services.items import (
    archive_item,
    get_item,
    hard_delete_item,
    list_items,
    restore_item,
    search_items,
    set_item_priority,
    set_item_reminder,
    set_item_stage,
    update_item_main_fields,
    update_repair_amounts,
    update_repair_client,
    update_resale_prices,
)
from app.states.common_states import CommonStates
from app.utils.calculations import parse_amount
from app.utils.constants import BUTTON_ACTIVE, BUTTON_SEARCH, CANCEL_TEXT
from app.utils.formatters import (
    format_client_history,
    format_item_card,
    format_item_stats,
    format_items_overview,
)


router = Router()


def parse_custom_reminder(raw_value: str) -> datetime:
    value = raw_value.strip().replace("/", ".")
    for pattern in ("%d.%m.%Y %H:%M", "%d.%m.%y %H:%M"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    raise ValueError("Используй формат ДД.ММ.ГГГГ ЧЧ:ММ. Пример: 09.04.2026 18:30")


async def send_item_card_message(message: Message, user_id: int, item_id: int) -> None:
    item = await get_item(user_id, item_id)
    if item is None:
        await message.answer("Устройство не найдено.", reply_markup=get_main_menu(is_admin=is_admin_user(user_id)))
        return

    await message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )


@router.message(Command("cancel"))
@router.message(F.text == CANCEL_TEXT)
async def cancel_action(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "Сейчас нечего отменять.",
            reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
        )
        return

    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )


@router.message(F.text == BUTTON_ACTIVE)
async def show_active_items(message: Message) -> None:
    items = await list_items(owner_tg_id=message.from_user.id, active_only=True, limit=20)

    if not items:
        await message.answer(
            "Сейчас нет активных устройств.",
            reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
        )
        return

    await message.answer(
        format_items_overview("Активные устройства", items),
        reply_markup=get_items_list_keyboard(items, "main:menu"),
    )


@router.message(F.text == BUTTON_SEARCH)
async def start_search(message: Message, state: FSMContext) -> None:
    await state.set_state(CommonStates.waiting_search_query)
    await message.answer(
        "Введи ID устройства или часть названия модели.\n\n"
        "Примеры: <code>15</code> или <code>iPhone 11</code>",
    )


@router.message(CommonStates.waiting_search_query)
async def process_search_query(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("Нужен ID или текст для поиска.")
        return

    items = await search_items(message.from_user.id, query)
    await state.clear()

    if not items:
        await message.answer(
            "Ничего не нашел.",
            reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
        )
        return

    await message.answer(
        format_items_overview(f"Результаты поиска по запросу: {query}", items),
        reply_markup=get_items_list_keyboard(items, "main:menu"),
    )


@router.callback_query(F.data == "main:menu")
async def close_inline_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    from app.handlers.start import show_home_screen

    await show_home_screen(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith("repair:view:"))
@router.callback_query(F.data.startswith("resale:view:"))
async def show_item_card(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await get_item(callback.from_user.id, item_id)

    if not item:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("repair:stats:"))
@router.callback_query(F.data.startswith("resale:stats:"))
async def show_item_stats(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await get_item(callback.from_user.id, item_id)

    if not item:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        format_item_stats(item),
        reply_markup=get_item_actions_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("repair:expenses:"))
@router.callback_query(F.data.startswith("resale:expenses:"))
async def show_expenses_for_delete(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await get_item(callback.from_user.id, item_id)

    if not item:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    if not item.expenses:
        await callback.answer("У этого устройства пока нет расходов.", show_alert=True)
        return

    await callback.message.answer(
        "Выбери расход, который нужно удалить.",
        reply_markup=get_expenses_list_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("expense:delete:"))
async def remove_expense(callback: CallbackQuery) -> None:
    expense_id = int(callback.data.split(":")[-1])
    item = await delete_expense(callback.from_user.id, expense_id)

    if not item:
        await callback.answer("Расход не найден.", show_alert=True)
        return

    await callback.message.answer("Расход удален.")
    await callback.message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item:edit:"))
async def show_item_edit_menu(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await get_item(callback.from_user.id, item_id)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        "Что хочешь изменить?",
        reply_markup=get_item_edit_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("itemedit:"))
async def request_item_edit_value(callback: CallbackQuery, state: FSMContext) -> None:
    _, field, item_id_raw = callback.data.split(":")
    item_id = int(item_id_raw)
    item = await get_item(callback.from_user.id, item_id)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    prompts = {
        "model": "Введи новую модель.",
        "note": "Введи новый комментарий. Чтобы очистить, отправь <code>-</code>.",
        "client": "Введи ФИО клиента. Чтобы очистить, отправь <code>-</code>.",
        "client_phone": "Введи телефон клиента. Чтобы очистить, отправь <code>-</code>.",
        "client_telegram": "Введи Telegram клиента: @username или ссылку. Чтобы очистить, отправь <code>-</code>.",
        "prepayment": "Введи новую сумму предоплаты.",
        "final": "Введи новую сумму при выдаче.",
        "buy": "Введи новую цену покупки.",
        "sell": "Введи новую цену продажи.",
    }

    await state.clear()
    await state.set_state(CommonStates.waiting_item_edit_value)
    await state.update_data(item_id=item_id, edit_field=field)
    await callback.message.answer(prompts.get(field, "Введи новое значение."))
    await callback.answer()


@router.message(CommonStates.waiting_item_edit_value)
async def process_item_edit_value(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    data = await state.get_data()
    item_id = data["item_id"]
    field = data["edit_field"]

    item = None
    if field == "model":
        if not raw_value:
            await message.answer("Модель не должна быть пустой.")
            return
        item = await update_item_main_fields(message.from_user.id, item_id, model=raw_value)
    elif field == "note":
        item = await update_item_main_fields(
            message.from_user.id,
            item_id,
            note="" if raw_value == "-" else raw_value,
        )
    elif field == "client":
        item = await update_repair_client(
            message.from_user.id,
            item_id,
            client_name="" if raw_value == "-" else raw_value,
        )
    elif field == "client_phone":
        item = await update_repair_client(
            message.from_user.id,
            item_id,
            phone="" if raw_value == "-" else raw_value,
        )
    elif field == "client_telegram":
        item = await update_repair_client(
            message.from_user.id,
            item_id,
            telegram_contact="" if raw_value == "-" else raw_value,
        )
    elif field == "prepayment":
        try:
            amount = parse_amount(raw_value, allow_zero=True)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        item = await update_repair_amounts(message.from_user.id, item_id, prepayment=amount)
    elif field == "final":
        try:
            amount = parse_amount(raw_value, allow_zero=True)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        item = await update_repair_amounts(message.from_user.id, item_id, final_received=amount)
    elif field == "buy":
        try:
            amount = parse_amount(raw_value, allow_zero=True)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        item = await update_resale_prices(message.from_user.id, item_id, buy_price=amount)
    elif field == "sell":
        try:
            amount = parse_amount(raw_value, allow_zero=True)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        item = await update_resale_prices(message.from_user.id, item_id, sell_price=amount)

    await state.clear()
    if item is None:
        await message.answer("Не удалось обновить заказ.")
        return

    await message.answer(
        "Заказ обновлен.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    await message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )


@router.callback_query(F.data.startswith("item:stage:"))
async def show_item_stage_menu(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await get_item(callback.from_user.id, item_id)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        "Выбери этап заказа.",
        reply_markup=get_item_stage_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item:set_stage:"))
async def update_item_stage_handler(callback: CallbackQuery) -> None:
    _, _, item_id_raw, stage = callback.data.split(":")
    item = await set_item_stage(callback.from_user.id, int(item_id_raw), stage)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )
    await callback.answer("Этап обновлен.")


@router.callback_query(F.data.startswith("item:priority:"))
async def show_item_priority_menu(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await get_item(callback.from_user.id, item_id)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        "Выбери приоритет заказа.",
        reply_markup=get_item_priority_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item:set_priority:"))
async def update_item_priority_handler(callback: CallbackQuery) -> None:
    _, _, item_id_raw, priority = callback.data.split(":")
    item = await set_item_priority(callback.from_user.id, int(item_id_raw), priority)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )
    await callback.answer("Приоритет обновлен.")


@router.callback_query(F.data.startswith("item:reminder:"))
async def show_item_reminder_menu(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await get_item(callback.from_user.id, item_id)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        "Выбери вариант напоминания.",
        reply_markup=get_item_reminder_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item:set_reminder:"))
async def set_item_reminder_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, item_id_raw, mode = callback.data.split(":")
    item_id = int(item_id_raw)

    if mode == "custom":
        await state.clear()
        await state.set_state(CommonStates.waiting_custom_reminder)
        await state.update_data(item_id=item_id)
        await callback.message.answer("Введи дату и время в формате <code>09.04.2026 18:30</code>.")
        await callback.answer()
        return

    if mode == "clear":
        reminder_at = None
    elif mode == "2h":
        reminder_at = datetime.now() + timedelta(hours=2)
    elif mode == "evening":
        now = datetime.now()
        reminder_at = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if reminder_at <= now:
            reminder_at = reminder_at + timedelta(days=1)
    else:
        tomorrow = datetime.now() + timedelta(days=1)
        reminder_at = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

    item = await set_item_reminder(callback.from_user.id, item_id, reminder_at)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )
    await callback.answer("Напоминание обновлено.")


@router.message(CommonStates.waiting_custom_reminder)
async def process_custom_reminder(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    try:
        reminder_at = parse_custom_reminder(raw_value)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    if reminder_at <= datetime.now():
        await message.answer("Дата напоминания должна быть в будущем.")
        return

    data = await state.get_data()
    item = await set_item_reminder(message.from_user.id, data["item_id"], reminder_at)
    await state.clear()
    if item is None:
        await message.answer("Устройство не найдено.")
        return

    await message.answer(
        "Напоминание сохранено.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    await message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )


@router.callback_query(F.data.startswith("item:archive:"))
async def archive_item_handler(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await archive_item(callback.from_user.id, item_id)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        "Заказ отправлен в архив.",
        reply_markup=get_main_menu(is_admin=is_admin_user(callback.from_user.id)),
    )
    await callback.message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item:delete:"))
async def delete_item_handler(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    deleted = await hard_delete_item(callback.from_user.id, item_id)
    if not deleted:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        "Заказ удален навсегда.",
        reply_markup=get_main_menu(is_admin=is_admin_user(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item:restore:"))
async def restore_item_handler(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":")[-1])
    item = await restore_item(callback.from_user.id, item_id)
    if item is None:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    await callback.message.answer(
        "Заказ восстановлен.",
        reply_markup=get_main_menu(is_admin=is_admin_user(callback.from_user.id)),
    )
    await callback.message.answer(
        format_item_card(item),
        reply_markup=get_item_actions_keyboard(item),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("client:view:"))
async def show_client_history(callback: CallbackQuery) -> None:
    client_id = int(callback.data.split(":")[-1])
    client, items = await get_client_history(callback.from_user.id, client_id)

    if client is None:
        await callback.answer("Клиент не найден.", show_alert=True)
        return

    await callback.message.answer(format_client_history(client, items))
    await callback.answer()
