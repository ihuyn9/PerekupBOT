import asyncio
import contextlib

from app.bot import bot, dp
from app.database.init_db import init_db
from app.handlers.admin import router as admin_router
from app.handlers.avito import router as avito_router
from app.handlers.common import router as common_router
from app.handlers.repairs import router as repairs_router
from app.handlers.resales import router as resales_router
from app.handlers.settings import router as settings_router
from app.handlers.start import router as start_router
from app.handlers.stats import router as stats_router
from app.middlewares.user_tracking import UserTrackingMiddleware
from app.services.avito import sync_all_avito_accounts
from app.services.reminders import get_due_reminders, mark_reminder_sent
from app.utils.formatters import format_item_card


async def avito_sync_loop() -> None:
    while True:
        try:
            await sync_all_avito_accounts()
        except Exception:
            pass
        await asyncio.sleep(60)


async def reminder_loop() -> None:
    while True:
        try:
            due_items = await get_due_reminders()
            for item in due_items:
                if item.owner_tg_id is None:
                    continue
                try:
                    await bot.send_message(
                        item.owner_tg_id,
                        "⏰ <b>Напоминание по заказу</b>\n\n" + format_item_card(item),
                    )
                    await mark_reminder_sent(item.id)
                except Exception:
                    continue
        except Exception:
            pass
        await asyncio.sleep(60)


async def main() -> None:
    await init_db()
    middleware = UserTrackingMiddleware()
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)
    sync_task = asyncio.create_task(avito_sync_loop())
    reminder_task = asyncio.create_task(reminder_loop())

    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(common_router)
    dp.include_router(settings_router)
    dp.include_router(avito_router)
    dp.include_router(repairs_router)
    dp.include_router(resales_router)
    dp.include_router(stats_router)

    print("Бот запускается...")
    try:
        await dp.start_polling(bot)
    finally:
        sync_task.cancel()
        reminder_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sync_task
        with contextlib.suppress(asyncio.CancelledError):
            await reminder_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен вручную.")
    except Exception as error:
        print(f"Ошибка при запуске бота: {error}")
