from datetime import datetime
from decimal import Decimal
from html import escape

from app.database.models import ActivityLog, AvitoAccount, AvitoChat, Client, Item, QuickReplyTemplate
from app.utils.calculations import (
    get_average_expense,
    get_days_in_work,
    get_expenses_count,
    get_expenses_total,
    get_margin_percent,
    get_profit,
    get_received_total,
    get_total_invested,
)
from app.utils.constants import (
    AVITO_CHAT_STAGE_LABELS,
    ITEM_KIND_REPAIR,
    ITEM_STAGE_LABELS,
    KIND_LABELS,
    PRIORITY_LABELS,
    STATUS_LABELS,
)


def format_money(amount: Decimal) -> str:
    value = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    if value.endswith(",00"):
        value = value[:-3]
    return f"{value} ₽"


def format_datetime(value: datetime | None) -> str:
    if not value:
        return "—"
    return value.strftime("%d.%m.%Y %H:%M")


def format_item_caption(item: Item) -> str:
    return f"#{item.id} • {item.model}"


def get_item_client_name(item: Item) -> str | None:
    if item.kind != ITEM_KIND_REPAIR or item.repair_details is None:
        return None
    if item.repair_details.client:
        return item.repair_details.client.full_name
    return item.repair_details.client_name


def format_item_card(item: Item) -> str:
    lines = [
        f"<b>{escape(format_item_caption(item))}</b>",
        f"{KIND_LABELS[item.kind]} • {STATUS_LABELS.get(item.status, item.status)}",
        f"Этап: {ITEM_STAGE_LABELS.get(item.stage, item.stage)}",
        f"Приоритет: {PRIORITY_LABELS.get(item.priority, item.priority)}",
    ]

    if item.reminder_at:
        lines.append(f"Напоминание: {format_datetime(item.reminder_at)}")

    if item.is_archived:
        lines.append("Статус хранения: в архиве")

    if item.kind == ITEM_KIND_REPAIR and item.repair_details:
        client = item.repair_details.client
        client_name = get_item_client_name(item) or "не указан"
        lines.append(f"Клиент: {escape(client_name)}")
        if client and client.phone:
            lines.append(f"Телефон: {escape(client.phone)}")
        if client and client.telegram_contact:
            lines.append(f"Telegram: {escape(client.telegram_contact)}")
        lines.append(f"Предоплата: {format_money(item.repair_details.prepayment_amount)}")
        lines.append(f"Получено при выдаче: {format_money(item.repair_details.final_received_amount)}")
    elif item.resale_details:
        lines.append(f"Покупка: {format_money(item.resale_details.buy_price)}")
        lines.append(f"Продажа: {format_money(item.resale_details.sell_price)}")

    lines.append(f"Расходы: {format_money(get_expenses_total(item))}")
    lines.append(f"Всего получено: {format_money(get_received_total(item))}")
    lines.append(f"Вложено: {format_money(get_total_invested(item))}")
    lines.append(f"Прибыль: {format_money(get_profit(item))}")

    if item.note:
        lines.append(f"Комментарий: {escape(item.note)}")

    if item.avito_chats:
        lines.extend(["", "<b>Avito</b>"])
        for chat in item.avito_chats[:3]:
            title = chat.client_name or chat.ad_title or "чат"
            lines.append(f"• {escape(title)} • этап: {AVITO_CHAT_STAGE_LABELS.get(chat.stage, chat.stage)}")

    if item.expenses:
        lines.extend(["", "<b>Последние расходы</b>"])
        for expense in sorted(item.expenses, key=lambda value: value.created_at, reverse=True)[:5]:
            expense_note = f" ({escape(expense.note)})" if expense.note else ""
            lines.append(f"• {escape(expense.title)} — {format_money(expense.amount)}{expense_note}")

    lines.extend(["", f"Создано: {format_datetime(item.created_at)}"])
    if item.closed_at:
        lines.append(f"Закрыто: {format_datetime(item.closed_at)}")
    if item.archived_at:
        lines.append(f"Архивировано: {format_datetime(item.archived_at)}")

    return "\n".join(lines)


def format_items_overview(title: str, items: list[Item]) -> str:
    if not items:
        return f"{title}\n\nПока список пуст."

    rows = [title, ""]
    for item in items:
        client = item.repair_details.client if item.kind == ITEM_KIND_REPAIR and item.repair_details else None
        client_name = get_item_client_name(item)
        extra_contacts = []
        if client_name:
            extra_contacts.append(f"клиент: {escape(client_name)}")
        if client and client.phone:
            extra_contacts.append(f"тел: {escape(client.phone)}")
        suffix = ", " + ", ".join(extra_contacts) if extra_contacts else ""
        archive_suffix = " • архив" if item.is_archived else ""
        reminder_suffix = " • есть напоминание" if item.reminder_at else ""

        rows.append(
            f"• #{item.id} — {escape(item.model)} "
            f"({KIND_LABELS[item.kind].lower()}, "
            f"{STATUS_LABELS.get(item.status, item.status).lower()}, "
            f"{ITEM_STAGE_LABELS.get(item.stage, item.stage).lower()}{suffix}{archive_suffix}{reminder_suffix})"
        )

    return "\n".join(rows)


def format_item_stats(item: Item) -> str:
    lines = [
        f"<b>Статистика по устройству #{item.id}</b>",
        f"Модель: {escape(item.model)}",
        f"Тип: {KIND_LABELS[item.kind]}",
        f"Статус: {STATUS_LABELS.get(item.status, item.status)}",
        f"Этап: {ITEM_STAGE_LABELS.get(item.stage, item.stage)}",
        f"Приоритет: {PRIORITY_LABELS.get(item.priority, item.priority)}",
        f"Создано: {format_datetime(item.created_at)}",
        f"Закрыто: {format_datetime(item.closed_at)}",
        f"Напоминание: {format_datetime(item.reminder_at)}",
        f"Дней в работе: {get_days_in_work(item)}",
        "",
        "<b>Финансы</b>",
        f"Получено: {format_money(get_received_total(item))}",
        f"Вложено: {format_money(get_total_invested(item))}",
        f"Расходы: {format_money(get_expenses_total(item))}",
        f"Прибыль: {format_money(get_profit(item))}",
        f"Маржа: {get_margin_percent(item)}%",
        "",
        "<b>Расходы</b>",
        f"Количество расходов: {get_expenses_count(item)}",
        f"Средний расход: {format_money(get_average_expense(item))}",
    ]

    if item.kind == ITEM_KIND_REPAIR and item.repair_details:
        client = item.repair_details.client
        client_name = get_item_client_name(item) or "не указан"
        lines.extend(
            [
                "",
                "<b>Клиентский ремонт</b>",
                f"Клиент: {escape(client_name)}",
                f"Телефон: {escape(client.phone) if client and client.phone else '—'}",
                f"Telegram: {escape(client.telegram_contact) if client and client.telegram_contact else '—'}",
                f"Предоплата: {format_money(item.repair_details.prepayment_amount)}",
                f"Получено при выдаче: {format_money(item.repair_details.final_received_amount)}",
            ]
        )
    elif item.resale_details:
        lines.extend(
            [
                "",
                "<b>Перепродажа</b>",
                f"Цена покупки: {format_money(item.resale_details.buy_price)}",
                f"Цена продажи: {format_money(item.resale_details.sell_price)}",
            ]
        )

    if item.note:
        lines.extend(["", f"Комментарий: {escape(item.note)}"])

    if item.expenses:
        lines.extend(["", "<b>Все расходы</b>"])
        for expense in sorted(item.expenses, key=lambda value: value.created_at):
            lines.append(
                f"• {format_datetime(expense.created_at)} — "
                f"{escape(expense.title)} — {format_money(expense.amount)}"
            )

    return "\n".join(lines)


def format_client_history(client: Client, items: list[Item]) -> str:
    active_items = [item for item in items if not item.closed_at]
    closed_items = [item for item in items if item.closed_at]
    last_visit = items[0].created_at if items else None

    lines = [
        f"<b>Клиент: {escape(client.full_name)}</b>",
        f"Телефон: {escape(client.phone) if client.phone else '—'}",
        f"Telegram: {escape(client.telegram_contact) if client.telegram_contact else '—'}",
        f"Всего обращений: {len(items)}",
        f"Активных ремонтов: {len(active_items)}",
        f"Закрытых ремонтов: {len(closed_items)}",
        f"Последнее обращение: {format_datetime(last_visit)}",
    ]

    if items:
        lines.extend(["", "<b>История</b>"])
        for item in items:
            lines.append(
                f"• #{item.id} — {escape(item.model)} — "
                f"{STATUS_LABELS.get(item.status, item.status).lower()} — "
                f"{format_datetime(item.created_at)}"
            )
    else:
        lines.extend(["", "История пока пустая."])

    return "\n".join(lines)


def format_settings_card(
    *,
    broadcast_enabled: bool,
    avito_account: AvitoAccount | None,
    templates_count: int = 0,
) -> str:
    lines = [
        "⚙️ <b>Настройки</b>",
        "",
        f"Рассылка об обновлениях: {'включена' if broadcast_enabled else 'выключена'}",
        f"Шаблонов быстрых ответов: {templates_count}",
    ]

    if avito_account is None:
        lines.extend(["", "<b>Avito</b>", "API пока не подключен."])
    else:
        lines.extend(
            [
                "",
                "<b>Avito</b>",
                f"Client ID: <code>{escape(avito_account.client_id)}</code>",
                f"Аккаунт Avito ID: <code>{avito_account.avito_user_id or 'не определен'}</code>",
                f"Синхронизация: {'включена' if avito_account.sync_enabled else 'выключена'}",
                f"Объявления на ремонт: {escape(avito_account.repair_ad_ids or 'не заданы')}",
                f"Последняя синхронизация: {format_datetime(avito_account.last_synced_at)}",
            ]
        )

    return "\n".join(lines)


def format_avito_chats_overview(chats: list[AvitoChat]) -> str:
    if not chats:
        return (
            "💬 <b>Avito-чаты</b>\n\n"
            "Пока диалогов нет.\n"
            "Подключи Avito в настройках и нажми обновление."
        )

    lines = ["💬 <b>Avito-чаты</b>", ""]
    for chat in chats[:20]:
        unread = f" • новых: {chat.unread_count}" if chat.unread_count else ""
        linked = f" • заказ #{chat.linked_item_id}" if chat.linked_item_id else ""
        lines.append(
            f"• {(chat.client_name or 'Клиент Avito')} — "
            f"{(chat.ad_title or 'Объявление')} — "
            f"{AVITO_CHAT_STAGE_LABELS.get(chat.stage, chat.stage)}{unread}{linked}"
        )

    return "\n".join(lines)


def format_avito_chat_card(chat: AvitoChat) -> str:
    lines = [
        "💬 <b>Диалог Avito</b>",
        f"Клиент: {escape(chat.client_name or 'Клиент Avito')}",
        f"Объявление: {escape(chat.ad_title or 'Без названия')}",
        f"Этап лида: {AVITO_CHAT_STAGE_LABELS.get(chat.stage, chat.stage)}",
        f"Привязанный заказ: {'#' + str(chat.linked_item_id) if chat.linked_item_id else 'нет'}",
        f"ID чата: <code>{chat.avito_chat_id}</code>",
        f"Новых сообщений: {chat.unread_count}",
        "",
        "<b>Переписка</b>",
    ]

    messages = sorted(chat.messages, key=lambda value: value.created_at)
    if not messages:
        lines.append("Сообщений пока нет.")
    else:
        for message in messages[-15:]:
            prefix = "🟢 Вы" if message.direction == "outgoing" else "🔵 Клиент"
            text = escape(message.text or "[без текста]")
            lines.append(f"{prefix} • {format_datetime(message.created_at)}")
            lines.append(text)
            lines.append("")

    return "\n".join(lines).strip()


def format_quick_replies_overview(templates: list[QuickReplyTemplate]) -> str:
    if not templates:
        return "⚡ <b>Шаблоны ответов</b>\n\nПока шаблонов нет."

    lines = ["⚡ <b>Шаблоны ответов</b>", ""]
    for template in templates:
        preview = template.text[:70].strip()
        if len(template.text) > 70:
            preview += "..."
        lines.append(f"• {escape(template.title)} — {escape(preview)}")
    return "\n".join(lines)


def format_activity_feed(logs: list[ActivityLog]) -> str:
    if not logs:
        return "📋 <b>Последняя активность</b>\n\nПока действий нет."

    lines = ["📋 <b>Последняя активность</b>", ""]
    for log in logs:
        lines.append(f"• {format_datetime(log.created_at)} — {escape(log.summary)}")
    return "\n".join(lines)
