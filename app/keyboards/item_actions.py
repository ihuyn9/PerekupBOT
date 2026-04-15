from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import Item
from app.utils.calculations import is_item_active
from app.utils.constants import (
    ITEM_KIND_REPAIR,
    PRIORITY_NORMAL,
    PRIORITY_URGENT,
    STAGE_BOUGHT,
    STAGE_DIAGNOSTICS,
    STAGE_IN_PROGRESS,
    STAGE_LISTED,
    STAGE_NEW,
    STAGE_PREP,
    STAGE_READY,
    STAGE_RESERVED,
    STAGE_WAITING_PARTS,
)
from app.utils.formatters import format_money


def get_item_actions_keyboard(item: Item) -> InlineKeyboardMarkup:
    item_prefix = "repair" if item.kind == ITEM_KIND_REPAIR else "resale"
    section_prefix = f"{item_prefix}s"
    rows: list[list[InlineKeyboardButton]] = []

    rows.append(
        [InlineKeyboardButton(text="📊 Статистика по устройству", callback_data=f"{item_prefix}:stats:{item.id}")]
    )
    rows.append(
        [InlineKeyboardButton(text="✏️ Редактировать заказ", callback_data=f"item:edit:{item.id}")]
    )
    rows.append(
        [
            InlineKeyboardButton(text="🧭 Этап", callback_data=f"item:stage:{item.id}"),
            InlineKeyboardButton(text="🚨 Приоритет", callback_data=f"item:priority:{item.id}"),
        ]
    )
    rows.append([InlineKeyboardButton(text="⏰ Напоминание", callback_data=f"item:reminder:{item.id}")])

    if is_item_active(item) and not item.is_archived and item.deleted_at is None:
        rows.append(
            [InlineKeyboardButton(text="💸 Добавить расход", callback_data=f"{item_prefix}:expense:{item.id}")]
        )

        if item.kind == ITEM_KIND_REPAIR:
            rows.append(
                [InlineKeyboardButton(text="💰 Добавить предоплату", callback_data=f"{item_prefix}:prepayment:{item.id}")]
            )
            rows.append(
                [InlineKeyboardButton(text="✅ Выдать клиенту", callback_data=f"{item_prefix}:close:{item.id}")]
            )
        else:
            rows.append(
                [InlineKeyboardButton(text="✅ Отметить как продано", callback_data=f"{item_prefix}:close:{item.id}")]
            )

    if item.expenses:
        rows.append(
            [InlineKeyboardButton(text="🗑 Удалить расход", callback_data=f"{item_prefix}:expenses:{item.id}")]
        )

    if item.kind == ITEM_KIND_REPAIR and item.repair_details and item.repair_details.client_id:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🧑 История клиента",
                    callback_data=f"client:view:{item.repair_details.client_id}",
                )
            ]
        )

    if item.is_archived:
        rows.append([InlineKeyboardButton(text="♻️ Восстановить из архива", callback_data=f"item:restore:{item.id}")])
    else:
        rows.append(
            [
                InlineKeyboardButton(text="🗄 В архив", callback_data=f"item:archive:{item.id}"),
                InlineKeyboardButton(text="🧨 Удалить навсегда", callback_data=f"item:delete:{item.id}"),
            ]
        )

    back_target = "archived" if item.is_archived else ("active" if is_item_active(item) else "closed")
    rows.append([InlineKeyboardButton(text="⬅️ К списку", callback_data=f"{section_prefix}:{back_target}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_item_edit_keyboard(item: Item) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📱 Модель", callback_data=f"itemedit:model:{item.id}")],
        [InlineKeyboardButton(text="📝 Комментарий", callback_data=f"itemedit:note:{item.id}")],
    ]

    if item.kind == ITEM_KIND_REPAIR:
        rows.extend(
            [
                [InlineKeyboardButton(text="🧑 ФИО клиента", callback_data=f"itemedit:client:{item.id}")],
                [InlineKeyboardButton(text="📞 Телефон клиента", callback_data=f"itemedit:client_phone:{item.id}")],
                [InlineKeyboardButton(text="💬 Telegram клиента", callback_data=f"itemedit:client_telegram:{item.id}")],
                [InlineKeyboardButton(text="💰 Предоплата", callback_data=f"itemedit:prepayment:{item.id}")],
                [InlineKeyboardButton(text="💵 Сумма при выдаче", callback_data=f"itemedit:final:{item.id}")],
            ]
        )
    else:
        rows.extend(
            [
                [InlineKeyboardButton(text="💳 Цена покупки", callback_data=f"itemedit:buy:{item.id}")],
                [InlineKeyboardButton(text="💸 Цена продажи", callback_data=f"itemedit:sell:{item.id}")],
            ]
        )

    rows.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{'repair' if item.kind == ITEM_KIND_REPAIR else 'resale'}:view:{item.id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_item_stage_keyboard(item: Item) -> InlineKeyboardMarkup:
    if item.kind == ITEM_KIND_REPAIR:
        stages = [
            (STAGE_NEW, "🆕 Новый"),
            (STAGE_DIAGNOSTICS, "🔎 Диагностика"),
            (STAGE_WAITING_PARTS, "🧩 Ждет запчасть"),
            (STAGE_IN_PROGRESS, "🛠 В работе"),
            (STAGE_READY, "📦 Готово"),
        ]
    else:
        stages = [
            (STAGE_BOUGHT, "🛒 Куплено"),
            (STAGE_PREP, "🧼 Подготовка"),
            (STAGE_LISTED, "📣 Выставлено"),
            (STAGE_RESERVED, "🤝 В резерве"),
        ]

    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"item:set_stage:{item.id}:{stage}")]
        for stage, label in stages
    ]
    rows.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{'repair' if item.kind == ITEM_KIND_REPAIR else 'resale'}:view:{item.id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_item_priority_keyboard(item: Item) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🙂 Обычный", callback_data=f"item:set_priority:{item.id}:{PRIORITY_NORMAL}")],
        [InlineKeyboardButton(text="🔥 Срочно", callback_data=f"item:set_priority:{item.id}:{PRIORITY_URGENT}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{'repair' if item.kind == ITEM_KIND_REPAIR else 'resale'}:view:{item.id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_item_reminder_keyboard(item: Item) -> InlineKeyboardMarkup:
    prefix = "repair" if item.kind == ITEM_KIND_REPAIR else "resale"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏱ Через 2 часа", callback_data=f"item:set_reminder:{item.id}:2h")],
            [InlineKeyboardButton(text="🌙 Сегодня вечером", callback_data=f"item:set_reminder:{item.id}:evening")],
            [InlineKeyboardButton(text="📅 Завтра в 10:00", callback_data=f"item:set_reminder:{item.id}:tomorrow")],
            [InlineKeyboardButton(text="⌨️ Ввести вручную", callback_data=f"item:set_reminder:{item.id}:custom")],
            [InlineKeyboardButton(text="🧹 Очистить", callback_data=f"item:set_reminder:{item.id}:clear")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{prefix}:view:{item.id}")],
        ]
    )


def get_items_list_keyboard(items: Sequence[Item], back_callback: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for item in items:
        prefix = "repair" if item.kind == ITEM_KIND_REPAIR else "resale"
        archive_marker = " [архив]" if item.is_archived else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📱 #{item.id} • {item.model}{archive_marker}",
                    callback_data=f"{prefix}:view:{item.id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_expenses_list_keyboard(item: Item) -> InlineKeyboardMarkup:
    prefix = "repair" if item.kind == ITEM_KIND_REPAIR else "resale"
    rows: list[list[InlineKeyboardButton]] = []

    for expense in sorted(item.expenses, key=lambda value: value.created_at, reverse=True):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 {expense.title} ({format_money(expense.amount)})",
                    callback_data=f"expense:delete:{expense.id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="⬅️ Назад к устройству", callback_data=f"{prefix}:view:{item.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
