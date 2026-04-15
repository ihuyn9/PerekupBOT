from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import AvitoAccount, BotUser


def get_settings_keyboard(user: BotUser, account: AvitoAccount | None) -> InlineKeyboardMarkup:
    broadcast_text = "🔕 Включить рассылку" if not user.broadcast_enabled else "🔔 Выключить рассылку"
    sync_text = (
        "⏸ Выключить синхронизацию Avito"
        if account and account.sync_enabled
        else "▶️ Включить синхронизацию Avito"
    )
    connect_text = "🔄 Обновить Avito API" if account else "🔗 Подключить Avito API"

    rows = [
        [InlineKeyboardButton(text=broadcast_text, callback_data="settings:broadcast")],
        [InlineKeyboardButton(text=connect_text, callback_data="settings:avito_connect")],
        [InlineKeyboardButton(text="🏷 Настроить ID объявлений на ремонт", callback_data="settings:avito_ads")],
        [InlineKeyboardButton(text=sync_text, callback_data="settings:avito_sync_toggle")],
        [InlineKeyboardButton(text="🔄 Обновить чаты сейчас", callback_data="settings:avito_sync_now")],
        [InlineKeyboardButton(text="⚡ Шаблоны ответов Avito", callback_data="settings:templates")],
        [InlineKeyboardButton(text="🧹 Полный сброс моих данных", callback_data="settings:reset_all")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
