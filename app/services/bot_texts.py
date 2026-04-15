from sqlalchemy import select

from app.database.models import BotText
from app.database.session import async_session
from app.utils.texts import DEFAULT_BOT_TEXTS


async def get_text(key: str) -> str:
    async with async_session() as session:
        result = await session.execute(select(BotText).where(BotText.key == key))
        text = result.scalar_one_or_none()
        if text is not None:
            return text.value

    return DEFAULT_BOT_TEXTS[key]


async def set_text(key: str, value: str) -> BotText:
    async with async_session() as session:
        result = await session.execute(select(BotText).where(BotText.key == key))
        text = result.scalar_one_or_none()

        if text is None:
            text = BotText(key=key, value=value)
            session.add(text)
        else:
            text.value = value

        await session.commit()
        await session.refresh(text)
        return text


async def list_texts() -> list[BotText]:
    async with async_session() as session:
        result = await session.execute(select(BotText).order_by(BotText.key))
        return list(result.scalars().all())
