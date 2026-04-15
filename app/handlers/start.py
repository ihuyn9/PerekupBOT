from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.keyboards.main_menu import get_main_menu
from app.services.bot_texts import get_text
from app.services.bot_users import is_admin_user
from app.utils.constants import BUTTON_MENU


router = Router()


async def show_home_screen(message: Message, user_id: int) -> None:
    text = await get_text("start_message")
    await message.answer(
        text,
        reply_markup=get_main_menu(is_admin=is_admin_user(user_id)),
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await show_home_screen(message, message.from_user.id)


@router.message(F.text == BUTTON_MENU)
async def show_main_menu(message: Message) -> None:
    await show_home_screen(message, message.from_user.id)
