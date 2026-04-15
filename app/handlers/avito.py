from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.avito_menu import (
    get_avito_chat_actions_keyboard,
    get_avito_chats_keyboard,
    get_avito_stage_keyboard,
    get_avito_templates_keyboard,
)
from app.keyboards.item_actions import get_item_actions_keyboard
from app.keyboards.main_menu import get_cancel_keyboard, get_main_menu
from app.services.avito import (
    AvitoApiError,
    get_avito_chat,
    link_chat_to_item,
    list_avito_chats,
    mark_chat_read,
    send_avito_reply,
    set_avito_chat_stage,
    sync_avito_account,
)
from app.services.bot_users import is_admin_user
from app.services.quick_replies import get_template, list_templates
from app.services.repairs import create_repair
from app.services.resales import create_resale
from app.states.avito_states import AvitoStates
from app.utils.constants import BUTTON_AVITO_CHATS
from app.utils.formatters import (
    format_avito_chat_card,
    format_avito_chats_overview,
    format_item_card,
    format_quick_replies_overview,
)


router = Router()


async def send_avito_chats_screen(message: Message, user_id: int) -> None:
    chats = await list_avito_chats(user_id)
    await message.answer(
        format_avito_chats_overview(chats),
        reply_markup=get_avito_chats_keyboard(chats),
    )


@router.message(F.text == BUTTON_AVITO_CHATS)
async def open_avito_chats(message: Message) -> None:
    await send_avito_chats_screen(message, message.from_user.id)


@router.callback_query(F.data == "avito:list")
@router.callback_query(F.data == "avito:refresh")
async def refresh_avito_chats(callback: CallbackQuery) -> None:
    if callback.data == "avito:refresh":
        try:
            await sync_avito_account(callback.from_user.id)
        except Exception:
            pass

    chats = await list_avito_chats(callback.from_user.id)
    await callback.message.answer(
        format_avito_chats_overview(chats),
        reply_markup=get_avito_chats_keyboard(chats),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("avito:chat:"))
@router.callback_query(F.data.startswith("avito:chat_refresh:"))
async def show_avito_chat(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[-1])
    if callback.data.startswith("avito:chat_refresh:"):
        chat = await get_avito_chat(callback.from_user.id, chat_id)
        if chat:
            try:
                await sync_avito_account(callback.from_user.id)
            except Exception:
                pass

    chat = await mark_chat_read(callback.from_user.id, chat_id)
    if chat is None:
        await callback.answer("Чат не найден.", show_alert=True)
        return

    await callback.message.answer(
        format_avito_chat_card(chat),
        reply_markup=get_avito_chat_actions_keyboard(chat.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("avito:reply:"))
async def request_avito_reply(callback: CallbackQuery, state: FSMContext) -> None:
    chat_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.set_state(AvitoStates.waiting_reply_text)
    await state.update_data(avito_chat_id=chat_id)
    await callback.message.answer(
        "Напиши ответ клиенту Avito одним сообщением.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(AvitoStates.waiting_reply_text)
async def process_avito_reply(message: Message, state: FSMContext) -> None:
    reply_text = (message.text or "").strip()
    if not reply_text:
        await message.answer("Текст ответа не должен быть пустым.")
        return

    data = await state.get_data()
    chat_id = data["avito_chat_id"]

    try:
        chat = await send_avito_reply(message.from_user.id, chat_id, reply_text)
    except AvitoApiError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer("Не удалось отправить сообщение в Avito.")
        return

    await state.clear()
    if chat is None:
        await message.answer("Чат не найден.", reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)))
        return

    await message.answer(
        "Сообщение отправлено в Avito.",
        reply_markup=get_main_menu(is_admin=is_admin_user(message.from_user.id)),
    )
    await message.answer(
        format_avito_chat_card(chat),
        reply_markup=get_avito_chat_actions_keyboard(chat.id),
    )


@router.callback_query(F.data.startswith("avito:templates:"))
async def show_avito_templates(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[-1])
    templates = await list_templates(callback.from_user.id)
    await callback.message.answer(
        format_quick_replies_overview(templates),
        reply_markup=get_avito_templates_keyboard(chat_id, templates),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("avito:template_send:"))
async def send_template_to_avito(callback: CallbackQuery) -> None:
    _, _, _, chat_id_raw, template_id_raw = callback.data.split(":")
    chat_id = int(chat_id_raw)
    template_id = int(template_id_raw)
    template = await get_template(callback.from_user.id, template_id)
    if template is None:
        await callback.answer("Шаблон не найден.", show_alert=True)
        return

    try:
        chat = await send_avito_reply(callback.from_user.id, chat_id, template.text)
    except AvitoApiError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    except Exception:
        await callback.answer("Не удалось отправить шаблон.", show_alert=True)
        return

    if chat:
        await callback.message.answer(
            format_avito_chat_card(chat),
            reply_markup=get_avito_chat_actions_keyboard(chat.id),
        )
    await callback.answer("Шаблон отправлен.")


@router.callback_query(F.data.startswith("avito:stage:"))
async def show_avito_stage_menu(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[-1])
    await callback.message.answer(
        "Выбери этап лида.",
        reply_markup=get_avito_stage_keyboard(chat_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("avito:set_stage:"))
async def update_avito_stage(callback: CallbackQuery) -> None:
    _, _, _, chat_id_raw, stage = callback.data.split(":")
    chat_id = int(chat_id_raw)
    chat = await set_avito_chat_stage(callback.from_user.id, chat_id, stage)
    if chat is None:
        await callback.answer("Чат не найден.", show_alert=True)
        return

    await callback.message.answer(
        format_avito_chat_card(chat),
        reply_markup=get_avito_chat_actions_keyboard(chat.id),
    )
    await callback.answer("Этап обновлен.")


@router.callback_query(F.data.startswith("avito:create_repair:"))
async def create_repair_from_avito_chat(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[-1])
    chat = await get_avito_chat(callback.from_user.id, chat_id)
    if chat is None:
        await callback.answer("Чат не найден.", show_alert=True)
        return

    item = await create_repair(
        owner_tg_id=callback.from_user.id,
        model=chat.ad_title or "Заявка с Avito",
        client_name=chat.client_name or "Клиент Avito",
        note=(
            f"Источник: Avito\n"
            f"Avito chat ID: {chat.avito_chat_id}\n"
            f"Avito ad ID: {chat.ad_id or 'не указан'}"
        ),
    )

    if item:
        await link_chat_to_item(callback.from_user.id, chat_id, item.id)

    await callback.message.answer("Ремонт создан из Avito-диалога.")
    if item:
        await callback.message.answer(
            format_item_card(item),
            reply_markup=get_item_actions_keyboard(item),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("avito:create_resale:"))
async def create_resale_from_avito_chat(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[-1])
    chat = await get_avito_chat(callback.from_user.id, chat_id)
    if chat is None:
        await callback.answer("Чат не найден.", show_alert=True)
        return

    item = await create_resale(
        owner_tg_id=callback.from_user.id,
        model=chat.ad_title or "Сделка с Avito",
        buy_price=Decimal("0"),
        note=(
            f"Источник: Avito\n"
            f"Avito chat ID: {chat.avito_chat_id}\n"
            f"Avito ad ID: {chat.ad_id or 'не указан'}"
        ),
    )

    if item:
        await link_chat_to_item(callback.from_user.id, chat_id, item.id)

    await callback.message.answer("Перепродажа создана из Avito-диалога.")
    if item:
        await callback.message.answer(
            format_item_card(item),
            reply_markup=get_item_actions_keyboard(item),
        )
    await callback.answer()
