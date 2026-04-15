from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import bot, dp
from app.config import get_config
from app.keyboards.admin_menu import (
    get_admin_panel_keyboard,
    get_admin_texts_keyboard,
    get_admin_user_actions_keyboard,
    get_admin_users_keyboard,
)
from app.keyboards.main_menu import get_cancel_keyboard, get_main_menu
from app.services.activity_logs import list_recent_activity
from app.services.bot_texts import get_text, set_text
from app.services.bot_users import (
    get_admin_dashboard_stats,
    get_broadcast_targets,
    get_user_stats,
    is_admin_user,
    list_users,
    list_users_with_disabled_broadcast,
    set_ban_status,
)
from app.states.admin_states import AdminStates
from app.utils.constants import BUTTON_ADMIN
from app.utils.formatters import format_activity_feed, format_datetime
from app.utils.texts import BOT_TEXT_TITLES


config = get_config()
router = Router()


def has_admin_access(user_id: int) -> bool:
    return is_admin_user(user_id)


def build_admin_dashboard_text(stats: dict) -> str:
    repo_url = escape(config.github_repo_url or "не указан")
    return (
        "🛠 <b>Админ-панель</b>\n\n"
        f"Всего пользователей: {stats['total_users']}\n"
        f"Активных за 7 дней: {stats['active_recently']}\n"
        f"Пользователей с заказами: {stats['users_with_orders']}\n"
        f"Активных заказов всего: {stats['active_orders']}\n"
        f"Заказов в архиве: {stats['archived_orders']}\n"
        f"Подключили Avito: {stats['avito_connected']}\n"
        f"Всего шаблонов ответов: {stats['templates_total']}\n"
        f"Забаненных пользователей: {stats['banned_users']}\n"
        f"Выключили рассылку: {stats['broadcast_disabled']}\n\n"
        f"GitHub repo: {repo_url}"
    )


def build_user_card(stats: dict) -> str:
    user = stats["user"]
    username = f"@{escape(user.username)}" if user.username else "не указан"
    status = "забанен" if user.is_banned else "активен"

    return (
        f"👤 <b>{escape(user.full_name)}</b>\n"
        f"Telegram ID: <code>{user.tg_id}</code>\n"
        f"Username: {username}\n"
        f"Статус: {status}\n"
        f"Первый запуск: {format_datetime(user.created_at)}\n"
        f"Последняя активность: {format_datetime(user.last_seen_at)}\n"
        f"Всего заказов: {stats['total_items']}\n"
        f"Активных заказов: {stats['active_items']}\n"
        f"В архиве: {stats['archived_items']}\n"
        f"Шаблонов ответов: {stats['templates_count']}"
    )


@router.message(Command("admin"))
@router.message(F.text == BUTTON_ADMIN)
async def open_admin_panel(message: Message) -> None:
    if not has_admin_access(message.from_user.id):
        await message.answer("У тебя нет доступа к админ-панели.")
        return

    stats = await get_admin_dashboard_stats()
    await message.answer(
        build_admin_dashboard_text(stats),
        reply_markup=get_admin_panel_keyboard(),
    )


@router.callback_query(F.data == "admin:panel")
async def show_admin_panel(callback: CallbackQuery) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    stats = await get_admin_dashboard_stats()
    await callback.message.answer(
        build_admin_dashboard_text(stats),
        reply_markup=get_admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def show_users(callback: CallbackQuery) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    users = await list_users()
    await callback.message.answer(
        "Пользователи бота:",
        reply_markup=get_admin_users_keyboard(users),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast_off")
async def show_broadcast_disabled_users(callback: CallbackQuery) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    users = await list_users_with_disabled_broadcast()
    if not users:
        await callback.message.answer("Пока никто не выключал рассылку.")
        await callback.answer()
        return

    lines = ["🔕 <b>Выключили рассылку</b>", ""]
    for user in users:
        username = f"@{escape(user.username)}" if user.username else "без username"
        lines.append(f"• {escape(user.full_name)} — {username} — {format_datetime(user.last_seen_at)}")

    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.callback_query(F.data == "admin:activity")
async def show_activity(callback: CallbackQuery) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    logs = await list_recent_activity(limit=30)
    await callback.message.answer(format_activity_feed(logs))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:"))
async def show_user_card(callback: CallbackQuery) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    tg_id = int(callback.data.split(":")[-1])
    stats = await get_user_stats(tg_id)

    if stats is None:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await callback.message.answer(
        build_user_card(stats),
        reply_markup=get_admin_user_actions_keyboard(stats["user"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:ban:"))
async def toggle_ban(callback: CallbackQuery) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    tg_id = int(callback.data.split(":")[-1])
    if config.admin_id is not None and tg_id == config.admin_id:
        await callback.answer("Админа забанить нельзя.", show_alert=True)
        return

    current = await get_user_stats(tg_id)
    if current is None:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    updated_user = await set_ban_status(tg_id, not current["user"].is_banned)
    updated_stats = await get_user_stats(tg_id)
    action_text = "Пользователь забанен." if updated_user and updated_user.is_banned else "Пользователь разбанен."

    await callback.message.answer(action_text)
    await callback.message.answer(
        build_user_card(updated_stats),
        reply_markup=get_admin_user_actions_keyboard(updated_stats["user"]),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def request_broadcast_text(callback: CallbackQuery, state: FSMContext) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.waiting_broadcast_text)
    await callback.message.answer(
        "Отправь текст рассылки одним сообщением.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_broadcast_text)
async def send_broadcast(message: Message, state: FSMContext) -> None:
    if not has_admin_access(message.from_user.id):
        await state.clear()
        await message.answer("Нет доступа.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Нужен текст для рассылки.")
        return

    targets = await get_broadcast_targets()
    success_count = 0
    fail_count = 0

    for user in targets:
        try:
            await bot.send_message(user.tg_id, text)
            success_count += 1
        except Exception:
            fail_count += 1

    await state.clear()
    await message.answer(
        f"Рассылка завершена.\nУспешно: {success_count}\nОшибок: {fail_count}",
        reply_markup=get_main_menu(is_admin=True),
    )


@router.callback_query(F.data == "admin:texts")
async def show_texts_menu(callback: CallbackQuery) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await callback.message.answer(
        "Выбери текст для изменения.",
        reply_markup=get_admin_texts_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:text:"))
async def request_text_value(callback: CallbackQuery, state: FSMContext) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    text_key = callback.data.split(":")[-1]
    if text_key not in BOT_TEXT_TITLES:
        await callback.answer("Неизвестный текст.", show_alert=True)
        return

    current_value = await get_text(text_key)

    await state.clear()
    await state.set_state(AdminStates.waiting_text_value)
    await state.update_data(text_key=text_key)
    await callback.message.answer(
        f"<b>{BOT_TEXT_TITLES[text_key]}</b>\n\n"
        f"Текущий текст:\n{escape(current_value)}\n\n"
        "Отправь новый текст одним сообщением.",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_text_value)
async def save_text_value(message: Message, state: FSMContext) -> None:
    if not has_admin_access(message.from_user.id):
        await state.clear()
        await message.answer("Нет доступа.")
        return

    data = await state.get_data()
    text_key = data["text_key"]
    if text_key not in BOT_TEXT_TITLES:
        await state.clear()
        await message.answer("Неизвестный текст.")
        return

    new_value = (message.text or "").strip()

    if not new_value:
        await message.answer("Текст не должен быть пустым.")
        return

    await set_text(text_key, new_value)
    await state.clear()
    await message.answer(
        f"Текст «{BOT_TEXT_TITLES[text_key]}» обновлен.",
        reply_markup=get_main_menu(is_admin=True),
    )


@router.callback_query(F.data == "admin:stop")
async def stop_bot(callback: CallbackQuery) -> None:
    if not has_admin_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await callback.message.answer("Останавливаю бота...")
    await callback.answer()
    await dp.stop_polling()
