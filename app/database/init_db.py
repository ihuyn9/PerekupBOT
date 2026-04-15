from pathlib import Path

from sqlalchemy import inspect

from app.config import get_config
from app.database.models import Base
from app.database.session import engine
from app.utils.constants import ITEM_KIND_REPAIR, STAGE_BOUGHT, STAGE_NEW
from app.utils.normalizers import normalize_person_name


config = get_config()


def _add_column_if_missing(sync_conn, table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(sync_conn)
    if table_name not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name not in columns:
        sync_conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def _apply_schema_migrations(sync_conn) -> None:
    _add_column_if_missing(sync_conn, "bot_users", "broadcast_enabled", "broadcast_enabled BOOLEAN DEFAULT 1")
    _add_column_if_missing(sync_conn, "items", "owner_tg_id", "owner_tg_id BIGINT")
    _add_column_if_missing(sync_conn, "repair_details", "client_id", "client_id INTEGER REFERENCES clients(id)")
    _add_column_if_missing(sync_conn, "clients", "phone", "phone VARCHAR(50)")
    _add_column_if_missing(sync_conn, "clients", "normalized_phone", "normalized_phone VARCHAR(50)")
    _add_column_if_missing(sync_conn, "clients", "telegram_contact", "telegram_contact VARCHAR(255)")
    _add_column_if_missing(
        sync_conn,
        "clients",
        "normalized_telegram_contact",
        "normalized_telegram_contact VARCHAR(255)",
    )

    _add_column_if_missing(sync_conn, "items", "stage", "stage VARCHAR(50) DEFAULT 'new'")
    _add_column_if_missing(sync_conn, "items", "priority", "priority VARCHAR(20) DEFAULT 'normal'")
    _add_column_if_missing(sync_conn, "items", "reminder_at", "reminder_at DATETIME")
    _add_column_if_missing(sync_conn, "items", "reminder_sent_at", "reminder_sent_at DATETIME")
    _add_column_if_missing(sync_conn, "items", "is_archived", "is_archived BOOLEAN DEFAULT 0")
    _add_column_if_missing(sync_conn, "items", "archived_at", "archived_at DATETIME")
    _add_column_if_missing(sync_conn, "items", "deleted_at", "deleted_at DATETIME")

    _add_column_if_missing(sync_conn, "avito_chats", "stage", "stage VARCHAR(50) DEFAULT 'new'")
    _add_column_if_missing(
        sync_conn,
        "avito_chats",
        "linked_item_id",
        "linked_item_id INTEGER REFERENCES items(id)",
    )


def _backfill_legacy_data(sync_conn) -> None:
    if config.admin_id is not None:
        admin_row = sync_conn.exec_driver_sql(
            "SELECT id FROM bot_users WHERE tg_id = ?",
            (config.admin_id,),
        ).fetchone()
        if admin_row is None:
            sync_conn.exec_driver_sql(
                """
                INSERT INTO bot_users (
                    tg_id,
                    username,
                    full_name,
                    is_admin,
                    is_banned,
                    broadcast_enabled,
                    created_at,
                    last_seen_at
                )
                VALUES (?, NULL, 'Admin', 1, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (config.admin_id,),
            )
        else:
            sync_conn.exec_driver_sql(
                "UPDATE bot_users SET is_admin = 1 WHERE tg_id = ?",
                (config.admin_id,),
            )

        sync_conn.exec_driver_sql(
            "UPDATE items SET owner_tg_id = ? WHERE owner_tg_id IS NULL",
            (config.admin_id,),
        )

        rows = sync_conn.exec_driver_sql(
            """
            SELECT rd.id, rd.client_name
            FROM repair_details rd
            JOIN items i ON i.id = rd.item_id
            WHERE rd.client_id IS NULL
              AND rd.client_name IS NOT NULL
              AND TRIM(rd.client_name) <> ''
              AND i.owner_tg_id = ?
            """,
            (config.admin_id,),
        ).fetchall()

        for repair_id, client_name in rows:
            normalized_name = normalize_person_name(client_name)
            existing_client = sync_conn.exec_driver_sql(
                """
                SELECT id
                FROM clients
                WHERE owner_tg_id = ?
                  AND normalized_name = ?
                """,
                (config.admin_id, normalized_name),
            ).fetchone()

            if existing_client:
                client_id = existing_client[0]
            else:
                result = sync_conn.exec_driver_sql(
                    """
                    INSERT INTO clients (owner_tg_id, full_name, normalized_name, note, created_at)
                    VALUES (?, ?, ?, NULL, CURRENT_TIMESTAMP)
                    """,
                    (config.admin_id, client_name.strip(), normalized_name),
                )
                client_id = result.lastrowid

            sync_conn.exec_driver_sql(
                "UPDATE repair_details SET client_id = ? WHERE id = ?",
                (client_id, repair_id),
            )

    sync_conn.exec_driver_sql(
        "UPDATE bot_users SET broadcast_enabled = 1 WHERE broadcast_enabled IS NULL"
    )
    sync_conn.exec_driver_sql(
        "UPDATE items SET stage = CASE WHEN kind = ? THEN ? ELSE ? END WHERE stage IS NULL OR TRIM(stage) = ''",
        (ITEM_KIND_REPAIR, STAGE_NEW, STAGE_BOUGHT),
    )
    sync_conn.exec_driver_sql(
        "UPDATE items SET priority = 'normal' WHERE priority IS NULL OR TRIM(priority) = ''"
    )
    sync_conn.exec_driver_sql(
        "UPDATE items SET is_archived = 0 WHERE is_archived IS NULL"
    )
    sync_conn.exec_driver_sql(
        "UPDATE avito_chats SET stage = 'new' WHERE stage IS NULL OR TRIM(stage) = ''"
    )
    sync_conn.exec_driver_sql(
        "UPDATE clients SET normalized_phone = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') "
        "WHERE phone IS NOT NULL AND (normalized_phone IS NULL OR TRIM(normalized_phone) = '')"
    )
    sync_conn.exec_driver_sql(
        "UPDATE clients SET normalized_telegram_contact = LOWER(COALESCE(telegram_contact, '')) "
        "WHERE telegram_contact IS NOT NULL AND (normalized_telegram_contact IS NULL OR TRIM(normalized_telegram_contact) = '')"
    )


async def init_db():
    database_path = engine.url.database
    if database_path and database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_schema_migrations)
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_backfill_legacy_data)
