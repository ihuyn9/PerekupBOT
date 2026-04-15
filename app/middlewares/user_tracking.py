from collections.abc import Awaitable, Callable
from typing import Any

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.services.bot_texts import get_text
from app.services.bot_users import register_user


class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)

        if from_user is None or from_user.is_bot:
            return await handler(event, data)

        user = await register_user(
            tg_id=from_user.id,
            full_name=from_user.full_name,
            username=from_user.username,
        )
        data["bot_user"] = user

        if user.is_banned and not user.is_admin:
            banned_text = await get_text("banned_text")

            if isinstance(event, Message):
                await event.answer(banned_text)
            elif isinstance(event, CallbackQuery):
                await event.answer(banned_text, show_alert=True)
            return None

        return await handler(event, data)
