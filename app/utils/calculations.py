from datetime import datetime
from decimal import Decimal, InvalidOperation
from math import ceil

from app.database.models import Item
from app.utils.constants import ITEM_KIND_REPAIR, STATUS_ACTIVE, ZERO


def parse_amount(raw_value: str, *, allow_zero: bool = False) -> Decimal:
    normalized = raw_value.replace(" ", "").replace(",", ".")

    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("Не получилось распознать сумму. Пример: 1500 или 1500.50") from exc

    if amount < 0 or (amount == 0 and not allow_zero):
        raise ValueError("Сумма должна быть больше нуля.")

    return amount.quantize(Decimal("0.01"))


def get_expenses_total(item: Item) -> Decimal:
    return sum((expense.amount for expense in item.expenses), start=ZERO)


def get_received_total(item: Item) -> Decimal:
    if item.kind == ITEM_KIND_REPAIR:
        repair = item.repair_details
        if not repair:
            return ZERO
        return repair.prepayment_amount + repair.final_received_amount

    resale = item.resale_details
    return resale.sell_price if resale else ZERO


def get_total_invested(item: Item) -> Decimal:
    expenses_total = get_expenses_total(item)

    if item.kind == ITEM_KIND_REPAIR:
        return expenses_total

    resale = item.resale_details
    buy_price = resale.buy_price if resale else ZERO
    return buy_price + expenses_total


def get_profit(item: Item) -> Decimal:
    if item.kind == ITEM_KIND_REPAIR:
        return get_received_total(item) - get_expenses_total(item)

    resale = item.resale_details
    buy_price = resale.buy_price if resale else ZERO
    return get_received_total(item) - buy_price - get_expenses_total(item)


def is_item_active(item: Item) -> bool:
    return item.status == STATUS_ACTIVE


def get_expenses_count(item: Item) -> int:
    return len(item.expenses)


def get_average_expense(item: Item) -> Decimal:
    count = get_expenses_count(item)
    if count == 0:
        return ZERO
    return (get_expenses_total(item) / Decimal(count)).quantize(Decimal("0.01"))


def get_margin_percent(item: Item) -> Decimal:
    invested = get_total_invested(item)
    if invested == ZERO:
        return ZERO

    return ((get_profit(item) / invested) * Decimal("100")).quantize(Decimal("0.01"))


def get_days_in_work(item: Item) -> int:
    end_date = item.closed_at or datetime.utcnow()
    delta = end_date - item.created_at
    return max(1, ceil(delta.total_seconds() / 86400))
