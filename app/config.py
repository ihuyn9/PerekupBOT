from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Config:
    bot_token: str
    admin_id: int | None
    database_url: str
    github_repo_url: str | None


def get_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/bot.db")

    if not bot_token:
        raise ValueError("Не найден BOT_TOKEN в .env")

    admin_id_raw = os.getenv("ADMIN_ID")
    admin_id = int(admin_id_raw) if admin_id_raw else None
    github_repo_url = os.getenv("GITHUB_REPO_URL")

    return Config(
        bot_token=bot_token,
        admin_id=admin_id,
        database_url=database_url,
        github_repo_url=github_repo_url,
    )
