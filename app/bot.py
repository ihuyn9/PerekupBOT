from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.config import get_config


config = get_config()

bot = Bot(
    token=config.bot_token,
    default=DefaultBotProperties(parse_mode="HTML"),
)
dp = Dispatcher()
