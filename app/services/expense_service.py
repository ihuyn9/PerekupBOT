from sqlalchemy import select

from app.database.models import Expense, Item
from app.database.session import async_session
from app.services.activity_logs import log_activity
from app.services.items import get_item
from app.utils.constants import STATUS_ACTIVE


async def add_expense(
    *,
    owner_tg_id: int,
    item_id: int,
    title: str,
    amount,
    note: str | None = None,
) -> Expense | None:
    async with async_session() as session:
        item = await session.get(Item, item_id)
        if not item or item.owner_tg_id != owner_tg_id or item.status != STATUS_ACTIVE:
            return None

        expense = Expense(
            item_id=item_id,
            title=title,
            amount=amount,
            note=note,
        )
        session.add(expense)
        await session.commit()
        await session.refresh(expense)
        expense_id = expense.id

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="expense",
        entity_id=expense_id,
        action="expense_added",
        summary=f"Добавлен расход к заказу #{item_id}: {title} на {amount}",
    )
    return expense


async def delete_expense(owner_tg_id: int, expense_id: int) -> Item | None:
    async with async_session() as session:
        result = await session.execute(
            select(Expense, Item)
            .join(Item, Item.id == Expense.item_id)
            .where(
                Expense.id == expense_id,
                Item.owner_tg_id == owner_tg_id,
            )
        )
        row = result.first()
        if row is None:
            return None

        expense, item = row
        item_id = item.id
        expense_title = expense.title
        await session.delete(expense)
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="expense",
        entity_id=expense_id,
        action="expense_deleted",
        summary=f"Удален расход из заказа #{item_id}: {expense_title}",
    )
    return await get_item(owner_tg_id, item_id)
