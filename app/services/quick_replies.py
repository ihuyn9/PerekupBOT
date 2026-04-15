from sqlalchemy import select

from app.database.models import QuickReplyTemplate
from app.database.session import async_session
from app.services.activity_logs import log_activity


DEFAULT_TEMPLATES = (
    (
        "Первичный ответ",
        "Здравствуйте! Напишите, пожалуйста, модель телефона и что именно случилось.",
    ),
    (
        "Стоимость диагностики",
        "Диагностика бесплатная. После проверки напишу точную стоимость и сроки ремонта.",
    ),
    (
        "Адрес и время",
        "Отправлю адрес и удобное время. Перед выездом просто напишите, чтобы я был на месте.",
    ),
)


async def ensure_default_templates(owner_tg_id: int) -> None:
    async with async_session() as session:
        existing_count = await session.scalar(
            select(QuickReplyTemplate.id).where(QuickReplyTemplate.owner_tg_id == owner_tg_id).limit(1)
        )
        if existing_count is not None:
            return

        for title, text in DEFAULT_TEMPLATES:
            session.add(
                QuickReplyTemplate(
                    owner_tg_id=owner_tg_id,
                    title=title,
                    text=text,
                )
            )
        await session.commit()


async def list_templates(owner_tg_id: int) -> list[QuickReplyTemplate]:
    async with async_session() as session:
        result = await session.execute(
            select(QuickReplyTemplate)
            .where(QuickReplyTemplate.owner_tg_id == owner_tg_id)
            .order_by(QuickReplyTemplate.updated_at.desc(), QuickReplyTemplate.id.desc())
        )
        return list(result.scalars().all())


async def get_template(owner_tg_id: int, template_id: int) -> QuickReplyTemplate | None:
    async with async_session() as session:
        result = await session.execute(
            select(QuickReplyTemplate).where(
                QuickReplyTemplate.id == template_id,
                QuickReplyTemplate.owner_tg_id == owner_tg_id,
            )
        )
        return result.scalar_one_or_none()


async def create_template(owner_tg_id: int, title: str, text: str) -> QuickReplyTemplate:
    async with async_session() as session:
        template = QuickReplyTemplate(
            owner_tg_id=owner_tg_id,
            title=title.strip(),
            text=text.strip(),
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        template_id = template.id

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="template",
        entity_id=template_id,
        action="template_created",
        summary=f"Создан шаблон ответа: {title.strip()}",
    )
    return template


async def update_template(
    owner_tg_id: int,
    template_id: int,
    *,
    title: str | None = None,
    text: str | None = None,
) -> QuickReplyTemplate | None:
    async with async_session() as session:
        result = await session.execute(
            select(QuickReplyTemplate).where(
                QuickReplyTemplate.id == template_id,
                QuickReplyTemplate.owner_tg_id == owner_tg_id,
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            return None

        if title is not None:
            template.title = title.strip()
        if text is not None:
            template.text = text.strip()

        await session.commit()
        await session.refresh(template)
        template_id = template.id
        template_title = template.title

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="template",
        entity_id=template_id,
        action="template_updated",
        summary=f"Обновлен шаблон ответа: {template_title}",
    )
    return template


async def delete_template(owner_tg_id: int, template_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(QuickReplyTemplate).where(
                QuickReplyTemplate.id == template_id,
                QuickReplyTemplate.owner_tg_id == owner_tg_id,
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            return False

        template_title = template.title
        await session.delete(template)
        await session.commit()

    await log_activity(
        owner_tg_id=owner_tg_id,
        actor_tg_id=owner_tg_id,
        entity_type="template",
        entity_id=template_id,
        action="template_deleted",
        summary=f"Удален шаблон ответа: {template_title}",
    )
    return True
