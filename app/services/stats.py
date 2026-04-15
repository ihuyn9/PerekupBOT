from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import Item
from app.database.session import async_session
from app.services.items import apply_owner_scope
from app.utils.calculations import get_expenses_total, get_profit
from app.utils.constants import ITEM_KIND_REPAIR, STATUS_ACTIVE, ZERO
from app.utils.formatters import format_money


LOAD_OPTIONS = (
    selectinload(Item.repair_details),
    selectinload(Item.resale_details),
    selectinload(Item.expenses),
)

MONTH_NAMES = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}


async def get_month_stats(owner_tg_id: int, year: int, month: int) -> str:
    async with async_session() as session:
        closed_result = await session.execute(
            apply_owner_scope(
                select(Item)
                .options(*LOAD_OPTIONS)
                .where(
                    Item.closed_at.is_not(None),
                    Item.deleted_at.is_(None),
                    Item.is_archived.is_(False),
                ),
                owner_tg_id,
            )
        )
        active_result = await session.execute(
            apply_owner_scope(
                select(Item)
                .options(*LOAD_OPTIONS)
                .where(
                    Item.status == STATUS_ACTIVE,
                    Item.deleted_at.is_(None),
                    Item.is_archived.is_(False),
                ),
                owner_tg_id,
            )
        )

        closed_items = [
            item
            for item in closed_result.scalars().all()
            if item.closed_at and item.closed_at.year == year and item.closed_at.month == month
        ]
        active_items = list(active_result.scalars().all())

    repair_items = [item for item in closed_items if item.kind == ITEM_KIND_REPAIR]
    resale_items = [item for item in closed_items if item.kind != ITEM_KIND_REPAIR]

    repair_received = sum(
        (
            (item.repair_details.prepayment_amount + item.repair_details.final_received_amount)
            if item.repair_details
            else ZERO
            for item in repair_items
        ),
        start=ZERO,
    )
    repair_expenses = sum((get_expenses_total(item) for item in repair_items), start=ZERO)
    repair_profit = sum((get_profit(item) for item in repair_items), start=ZERO)

    resale_buy_total = sum(
        (item.resale_details.buy_price if item.resale_details else ZERO for item in resale_items),
        start=ZERO,
    )
    resale_sell_total = sum(
        (item.resale_details.sell_price if item.resale_details else ZERO for item in resale_items),
        start=ZERO,
    )
    resale_expenses = sum((get_expenses_total(item) for item in resale_items), start=ZERO)
    resale_profit = sum((get_profit(item) for item in resale_items), start=ZERO)

    active_repairs = [item for item in active_items if item.kind == ITEM_KIND_REPAIR]
    active_resales = [item for item in active_items if item.kind != ITEM_KIND_REPAIR]

    month_title = f"{MONTH_NAMES[month]} {year}"
    total_profit = repair_profit + resale_profit

    return (
        f"<b>Статистика за {month_title}</b>\n\n"
        f"<b>Ремонты</b>\n"
        f"Закрыто: {len(repair_items)}\n"
        f"Получено: {format_money(repair_received)}\n"
        f"Расходы: {format_money(repair_expenses)}\n"
        f"Прибыль: {format_money(repair_profit)}\n\n"
        f"<b>Перепродажи</b>\n"
        f"Закрыто: {len(resale_items)}\n"
        f"Покупка: {format_money(resale_buy_total)}\n"
        f"Продажа: {format_money(resale_sell_total)}\n"
        f"Доп. расходы: {format_money(resale_expenses)}\n"
        f"Прибыль: {format_money(resale_profit)}\n\n"
        f"<b>Итого</b>\n"
        f"Закрытых устройств: {len(closed_items)}\n"
        f"Чистая прибыль: {format_money(total_profit)}\n\n"
        f"<b>Сейчас в работе</b>\n"
        f"Активных ремонтов: {len(active_repairs)}\n"
        f"Активных перепродаж: {len(active_resales)}"
    )
