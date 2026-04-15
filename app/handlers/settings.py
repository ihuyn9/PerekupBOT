from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.main_menu import get_cancel_keyboard, get_main_menu
from app.keyboards.settings_menu import get_settings_keyboard
from app.keyboards.template_menu import get_templates_management_keyboard
from app.services.avito import (
    AvitoApiError,
    get_avito_account,
    save_avito_account,
    set_avito_sync_enabled,
    sync_avito_account,
    update_avito_repair_ads,
)
from app.services.bot_users import get_user, is_admin_user, set_broadcast_enabled
from app.services.items import reset_user_data
from app.services.quick_replies import create_template, delete_template, get_template, list_templates, update_template
from app.states.settings_states import SettingsStates
from app.utils.constants import BUTTON_SETTINGS
from app.utils.formatters import format_quick_replies_overview, format_settings_card


router = Router()


async def send_settings_screen(message: Message, user_id: int) -> None:
    user = await get_user(user_id)
    account = await get_avito_account(user_id)
    templates = await list_templates(user_id)
    if user is None:
        return

    await message.answer(
        format_settings_card(
            broadcast_enabled=user.broadcast_enabled,
            avito_account=account,
            templates_count=len(templates),
        ),
        reply_markup=get_settings_keyboard(user, account),
    )


async def send_templates_screen(message: Message, user_id: int) -> None:
    templates = await list_templates(user_id)
    await message.answer(
        format_quick_replies_overview(templates),
        reply_markup=get_templates_management_keyboard(templates),
    )


@router.message(F.text == BUTTON_SETTINGS)
async def open_settings(message: Message) -> None:
    await send_settings_screen(message, message.from_user.id)


@router.callback_query(F.data == "settings:back")
async def back_to_settings(callback: CallbackQuery) -> None:
    await send_settings_screen(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "settings:broadcast")
async def toggle_broadcast(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    if user is None:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    updated_user = await set_broadcast_enabled(callback.from_user.id, not user.broadcast_enabled)
    account = await get_avito_account(callback.from_user.id)
    templates = await list_templates(callback.from_user.id)
    await callback.message.answer(
        format_settings_card(
            broadcast_enabled=updated_user.broadcast_enabled,
            avito_account=account,
            templates_count=len(templates),
        ),
        reply_markup=get_settings_keyboard(updated_user, account),
    )
    await callback.answer("Настройка обновлена.")


@router.callback_query(F.data == "settings:avito_connect")
async def request_avito_client_id(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SettingsStates.waiting_avito_client_id)
    await callback.message.answer(
        "Отправь <b>client_id</b> от Avito API.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_avito_client_id)
async def process_avito_client_id(message: Message, state: FSMContext) -> None:
    client_id = (message.text or "").strip()
    if not client_id:
        await message.answer("client_id не должен быть пустым.")
        return

    await state.update_data(avito_client_id=client_id)
    await state.set_state(SettingsStates.waiting_avito_client_secret)
    await message.answer("Теперь отправь <b>client_secret</b> от Avito API.")


@router.message(SettingsStates.waiting_avito_client_secret)
async def process_avito_client_secret(message: Message, state: FSMContext) -> None:
    client_secret = (message.text or "").strip()
    if not client_secret:
        await message.answer("client_secret не должен быть пустым.")
        return

    data = await state.get_data()
    await save_avito_account(
        owner_tg_id=message.from_user.id,
        client_id=data["avito_client_id"],
        client_secret=client_secret,
    )
    await state.clear()
    await message.answer(
        "Avito API сохранен. Теперь можно настроить ID объявлений на ремонт и сделать синхронизацию.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    await send_settings_screen(message, message.from_user.id)


@router.callback_query(F.data == "settings:avito_ads")
async def request_repair_ad_ids(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SettingsStates.waiting_avito_repair_ad_ids)
    await callback.message.answer(
        "Отправь ID объявлений на ремонт через запятую.\n\n"
        "Пример: <code>123456789,987654321</code>\n"
        "Если хочешь очистить список и подтягивать все Avito-чаты аккаунта, отправь <code>-</code>.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_avito_repair_ad_ids)
async def process_repair_ad_ids(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    if raw_value == "-":
        raw_value = ""

    account = await update_avito_repair_ads(message.from_user.id, raw_value)
    await state.clear()

    if account is None:
        await message.answer("Сначала подключи Avito API.")
        return

    await message.answer(
        "Список объявлений сохранен.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    await send_settings_screen(message, message.from_user.id)


@router.callback_query(F.data == "settings:avito_sync_toggle")
async def toggle_avito_sync(callback: CallbackQuery) -> None:
    account = await get_avito_account(callback.from_user.id)
    if account is None:
        await callback.answer("Сначала подключи Avito API.", show_alert=True)
        return

    updated = await set_avito_sync_enabled(callback.from_user.id, not account.sync_enabled)
    user = await get_user(callback.from_user.id)
    templates = await list_templates(callback.from_user.id)
    await callback.message.answer(
        format_settings_card(
            broadcast_enabled=user.broadcast_enabled if user else True,
            avito_account=updated,
            templates_count=len(templates),
        ),
        reply_markup=get_settings_keyboard(user, updated),
    )
    await callback.answer("Настройка синхронизации обновлена.")


@router.callback_query(F.data == "settings:avito_sync_now")
async def sync_avito_now(callback: CallbackQuery) -> None:
    try:
        result = await sync_avito_account(callback.from_user.id)
    except AvitoApiError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    except Exception:
        await callback.answer("Не удалось синхронизировать Avito. Проверь API и права доступа.", show_alert=True)
        return

    user = await get_user(callback.from_user.id)
    account = await get_avito_account(callback.from_user.id)
    templates = await list_templates(callback.from_user.id)
    await callback.message.answer(
        f"Синхронизация завершена.\nНовых чатов: {result['created_chats']}\nНовых сообщений: {result['new_messages']}"
    )
    await callback.message.answer(
        format_settings_card(
            broadcast_enabled=user.broadcast_enabled if user else True,
            avito_account=account,
            templates_count=len(templates),
        ),
        reply_markup=get_settings_keyboard(user, account),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:templates")
async def open_templates(callback: CallbackQuery) -> None:
    await send_templates_screen(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "settings:reset_all")
async def request_full_reset(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SettingsStates.waiting_reset_confirmation)
    await callback.message.answer(
        "Это удалит все твои заказы, клиентов, Avito-настройки и шаблоны ответов.\n\n"
        "Если точно хочешь начать с нуля, отправь сообщением слово <code>УДАЛИТЬ</code>.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_reset_confirmation)
async def process_full_reset(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip().upper() != "УДАЛИТЬ":
        await message.answer("Для полного сброса отправь именно слово <code>УДАЛИТЬ</code> или нажми отмену.")
        return

    await reset_user_data(message.from_user.id)
    await state.clear()
    await message.answer(
        "Все твои данные очищены. Бот снова в пустом состоянии.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    await send_settings_screen(message, message.from_user.id)


@router.callback_query(F.data == "settings:template_new")
async def start_template_creation(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SettingsStates.waiting_template_title)
    await callback.message.answer(
        "Отправь название шаблона.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_template_title)
async def process_template_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым.")
        return

    await state.update_data(template_title=title)
    await state.set_state(SettingsStates.waiting_template_text)
    await message.answer("Теперь отправь сам текст шаблона.")


@router.message(SettingsStates.waiting_template_text)
async def process_template_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст шаблона не должен быть пустым.")
        return

    data = await state.get_data()
    await create_template(message.from_user.id, data["template_title"], text)
    await state.clear()
    await message.answer(
        "Шаблон сохранен.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    await send_templates_screen(message, message.from_user.id)


@router.callback_query(F.data.startswith("settings:template_edit:"))
async def start_template_edit(callback: CallbackQuery, state: FSMContext) -> None:
    template_id = int(callback.data.split(":")[-1])
    template = await get_template(callback.from_user.id, template_id)
    if template is None:
        await callback.answer("Шаблон не найден.", show_alert=True)
        return

    await state.clear()
    await state.set_state(SettingsStates.waiting_template_edit_value)
    await state.update_data(template_id=template_id)
    await callback.message.answer(
        f"<b>{template.title}</b>\n\nТекущий текст:\n{template.text}\n\nОтправь новый текст шаблона.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_template_edit_value)
async def process_template_edit(message: Message, state: FSMContext) -> None:
    new_value = (message.text or "").strip()
    if not new_value:
        await message.answer("Текст не должен быть пустым.")
        return

    data = await state.get_data()
    template = await update_template(message.from_user.id, data["template_id"], text=new_value)
    await state.clear()
    if template is None:
        await message.answer("Шаблон не найден.")
        return

    await message.answer(
        "Шаблон обновлен.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    await send_templates_screen(message, message.from_user.id)


@router.callback_query(F.data.startswith("settings:template_delete:"))
async def remove_template(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":")[-1])
    deleted = await delete_template(callback.from_user.id, template_id)
    if not deleted:
        await callback.answer("Шаблон не найден.", show_alert=True)
        return

    await send_templates_screen(callback.message, callback.from_user.id)
    await callback.answer("Шаблон удален.")
