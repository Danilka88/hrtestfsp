"""Справочные данные: специализации, грейды, категории и банк заданий.

Заполнение идемпотентно: повторный вызов ничего не дублирует. Выполняется при
старте приложения, поэтому демо-стенд сразу содержит рабочие справочники.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.testing import Category, Grade, Item, Specialization
from app.services.item_factory import generate_items
from app.services.testing import GRADE_ORDER

logger = logging.getLogger(__name__)

# Короткая ссылка на кандидата. Формат используется в подборках, откликах,
# заданиях и приглашениях, поэтому живёт в одном месте: сторона, которая
# строит ссылку, и сторона, которая её разбирает, обязаны совпадать.
CANDIDATE_REFERENCE_PREFIX = "cand-"


def candidate_reference(user_id: str) -> str:
    """Ссылка на кандидата вида cand-8049f321."""
    return f"{CANDIDATE_REFERENCE_PREFIX}{user_id[:8]}"


SPECIALIZATIONS: list[tuple[str, str]] = [
    ("backend", "Backend-разработчик"),
    ("frontend", "Frontend-разработчик"),
    ("fullstack", "Fullstack-разработчик"),
    ("devops", "DevOps / SRE"),
    ("qa", "QA-инженер"),
    ("analyst", "Системный аналитик"),
    ("data", "Data / ML инженер"),
    ("mobile", "Мобильный разработчик"),
]

GRADE_TITLES: dict[str, str] = {
    "intern": "Стажёр (Intern)",
    "junior": "Младший (Junior)",
    "junior_plus": "Младший+ (Junior+)",
    "middle": "Средний (Middle)",
    "senior": "Старший (Senior)",
    "lead": "Ведущий (Lead)",
}


async def specialization_by_code(session: AsyncSession, code: str | None) -> Specialization | None:
    """Справочная запись по коду. `None` — код не задан или не найден.

    Решение, что делать с ненайденным кодом (ответ 404 или пропуск), остаётся за
    вызывающим: у подбора и у вакансий разные правила, а поиск записи — один.
    """
    if not code:
        return None
    return (
        await session.execute(select(Specialization).where(Specialization.code == code))
    ).scalar_one_or_none()


async def specialization_id(session: AsyncSession, code: str | None) -> int | None:
    record = await specialization_by_code(session, code)
    return record.id if record else None


async def specialization_code(session: AsyncSession, specialization_id: int | None) -> str | None:
    if specialization_id is None:
        return None
    record = await session.get(Specialization, specialization_id)
    return record.code if record else None


async def specialization_maps(session: AsyncSession) -> tuple[dict[int, str], dict[str, str]]:
    """Отображения «id → код» и «код → название» за один запрос."""
    rows = (await session.execute(select(Specialization))).scalars().all()
    return {row.id: row.code for row in rows}, {row.code: row.title for row in rows}


async def ensure_reference_data(session: AsyncSession) -> dict[str, int]:
    """Гарантирует наличие справочников и непустого банка заданий."""
    created: dict[str, int] = {"specializations": 0, "grades": 0, "categories": 0, "items": 0}

    existing_specs = {code for (code,) in (await session.execute(select(Specialization.code))).all()}
    for code, title in SPECIALIZATIONS:
        if code not in existing_specs:
            session.add(Specialization(code=code, title=title))
            created["specializations"] += 1

    existing_grades = {code for (code,) in (await session.execute(select(Grade.code))).all()}
    for order, code in enumerate(GRADE_ORDER):
        if code not in existing_grades:
            session.add(Grade(code=code, title=GRADE_TITLES.get(code, code), rank_order=order))
            created["grades"] += 1

    await session.flush()

    specs = (await session.execute(select(Specialization))).scalars().all()
    grades = (await session.execute(select(Grade))).scalars().all()

    existing_categories = {
        (spec_id, grade_code)
        for spec_id, grade_code in (
            await session.execute(select(Category.specialization_id, Category.grade_code))
        ).all()
    }
    for spec in specs:
        for grade in grades:
            if (spec.id, grade.code) not in existing_categories:
                session.add(Category(specialization_id=spec.id, grade_code=grade.code))
                created["categories"] += 1

    item_count = await session.scalar(select(func.count()).select_from(Item))
    if not item_count:
        default_spec = next((s for s in specs if s.code == "backend"), specs[0] if specs else None)
        for generated in generate_items():
            session.add(
                Item(
                    specialization_id=default_spec.id if default_spec else None,
                    skill_tag=generated.skill_tag,
                    difficulty=generated.difficulty,
                    payload=generated.payload,
                )
            )
            created["items"] += 1

    await session.commit()
    if any(created.values()):
        logger.info("справочные данные инициализированы: %s", created)
    return created
