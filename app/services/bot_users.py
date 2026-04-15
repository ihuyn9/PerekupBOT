from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.config import get_config
from app.database.models import AvitoAccount, BotUser, Item, QuickReplyTemplate
from app.database.session import async_session
from app.utils.constants import STATUS_ACTIVE


config = get_config()


def is_admin_user(tg_id: int) -> bool:
    return config.admin_id is not None and tg_id == config.admin_id


async def register_user(
    *,
    tg_id: int,
    full_name: str,
    username: str | None,
) -> BotUser:
    async with async_session() as session:
        result = await session.execute(select(BotUser).where(BotUser.tg_id == tg_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = BotUser(
                tg_id=tg_id,
                full_name=full_name,
                username=username,
                is_admin=is_admin_user(tg_id),
                is_banned=False,
                created_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
            )
            session.add(user)
        else:
            user.full_name = full_name
            user.username = username
            user.is_admin = is_admin_user(tg_id)
            user.last_seen_at = datetime.utcnow()

        await session.commit()
        await session.refresh(user)
        return user


async def get_user(tg_id: int) -> BotUser | None:
    async with async_session() as session:
        result = await session.execute(select(BotUser).where(BotUser.tg_id == tg_id))
        return result.scalar_one_or_none()


async def list_users(limit: int = 50) -> list[BotUser]:
    async with async_session() as session:
        result = await session.execute(
            select(BotUser).order_by(BotUser.last_seen_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


async def list_users_with_disabled_broadcast(limit: int = 50) -> list[BotUser]:
    async with async_session() as session:
        result = await session.execute(
            select(BotUser)
            .where(BotUser.broadcast_enabled.is_(False))
            .order_by(BotUser.last_seen_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def set_ban_status(tg_id: int, is_banned: bool) -> BotUser | None:
    async with async_session() as session:
        result = await session.execute(select(BotUser).where(BotUser.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        user.is_banned = is_banned
        await session.commit()
        await session.refresh(user)
        return user


async def set_broadcast_enabled(tg_id: int, enabled: bool) -> BotUser | None:
    async with async_session() as session:
        result = await session.execute(select(BotUser).where(BotUser.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        user.broadcast_enabled = enabled
        await session.commit()
        await session.refresh(user)
        return user


async def get_user_stats(tg_id: int) -> dict | None:
    async with async_session() as session:
        user_result = await session.execute(select(BotUser).where(BotUser.tg_id == tg_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            return None

        total_items = await session.scalar(
            select(func.count(Item.id)).where(Item.owner_tg_id == tg_id)
        )
        active_items = await session.scalar(
            select(func.count(Item.id)).where(
                Item.owner_tg_id == tg_id,
                Item.status == STATUS_ACTIVE,
                Item.deleted_at.is_(None),
                Item.is_archived.is_(False),
            )
        )
        archived_items = await session.scalar(
            select(func.count(Item.id)).where(
                Item.owner_tg_id == tg_id,
                Item.is_archived.is_(True),
                Item.deleted_at.is_(None),
            )
        )
        templates_count = await session.scalar(
            select(func.count(QuickReplyTemplate.id)).where(QuickReplyTemplate.owner_tg_id == tg_id)
        )

        return {
            "user": user,
            "total_items": total_items or 0,
            "active_items": active_items or 0,
            "archived_items": archived_items or 0,
            "templates_count": templates_count or 0,
        }


async def get_admin_dashboard_stats() -> dict:
    async with async_session() as session:
        total_users = await session.scalar(select(func.count(BotUser.id)))
        banned_users = await session.scalar(
            select(func.count(BotUser.id)).where(BotUser.is_banned.is_(True))
        )
        users_with_orders = await session.scalar(
            select(func.count(func.distinct(Item.owner_tg_id))).where(Item.owner_tg_id.is_not(None))
        )
        active_orders = await session.scalar(
            select(func.count(Item.id)).where(
                Item.status == STATUS_ACTIVE,
                Item.deleted_at.is_(None),
                Item.is_archived.is_(False),
            )
        )
        archived_orders = await session.scalar(
            select(func.count(Item.id)).where(
                Item.deleted_at.is_(None),
                Item.is_archived.is_(True),
            )
        )
        recent_border = datetime.utcnow() - timedelta(days=7)
        active_recently = await session.scalar(
            select(func.count(BotUser.id)).where(BotUser.last_seen_at >= recent_border)
        )
        broadcast_disabled = await session.scalar(
            select(func.count(BotUser.id)).where(BotUser.broadcast_enabled.is_(False))
        )
        avito_connected = await session.scalar(select(func.count(AvitoAccount.id)))
        templates_total = await session.scalar(select(func.count(QuickReplyTemplate.id)))

        return {
            "total_users": total_users or 0,
            "banned_users": banned_users or 0,
            "users_with_orders": users_with_orders or 0,
            "active_orders": active_orders or 0,
            "archived_orders": archived_orders or 0,
            "active_recently": active_recently or 0,
            "broadcast_disabled": broadcast_disabled or 0,
            "avito_connected": avito_connected or 0,
            "templates_total": templates_total or 0,
        }


async def get_broadcast_targets() -> list[BotUser]:
    async with async_session() as session:
        result = await session.execute(
            select(BotUser).where(
                BotUser.is_banned.is_(False),
                BotUser.is_admin.is_(False),
                BotUser.broadcast_enabled.is_(True),
            )
        )
        return list(result.scalars().all())
