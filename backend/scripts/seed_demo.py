"""Демонстрационные данные для стенда.

Создаёт кандидатов с определёнными категориями (в том числе профиль без истории
ФСП) и работодателей. Идемпотентно: повторный запуск не дублирует записи.

Запуск в контейнере: docker compose exec -T backend python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Позволяет запускать скрипт и как `python scripts/seed_demo.py`, и как `python -m scripts.seed_demo`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, utcnow
from app.db.session import dispose_engine, get_session_factory
from app.models.candidate import CandidateProfile
from app.models.employer import EmployerNeed, EmployerProfile, SelectionCandidate
from app.models.marketplace import Vacancy
from app.models.testing import SESSION_COMPLETED, Specialization, TestSession
from app.models.user import User, UserRole
from app.services.reference import ensure_reference_data

DEMO_PASSWORD = "demo12345"
DEMO_ADMIN_EMAIL = "admin@demo.ru"

DEMO_CANDIDATES: list[dict[str, Any]] = [
    {
        "email": "anna.kovaleva@demo.ru",
        "name": "Анна Ковалёва",
        "specialization": "backend",
        "grade": "senior",
        "theta": 1.4,
        "years": 7,
        "fsp_id": "fsp-1001",
        "stack": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Redis"],
        "summary": "Проектирую высоконагруженные сервисы, наставник в команде.",
    },
    {
        "email": "dmitry.sokolov@demo.ru",
        "name": "Дмитрий Соколов",
        "specialization": "backend",
        "grade": "middle",
        "theta": 0.6,
        "years": 4,
        "fsp_id": None,
        "stack": ["Python", "Django", "PostgreSQL", "Docker", "Kafka"],
        "summary": "Разрабатываю внутренние сервисы, люблю аккуратные миграции.",
    },
    {
        "email": "olga.nikolaeva@demo.ru",
        "name": "Ольга Николаева",
        "specialization": "backend",
        "grade": "junior",
        "theta": -0.7,
        "years": 1,
        "fsp_id": "fsp-2000",
        "stack": ["Python", "Flask", "SQL", "Git"],
        "summary": "Первая работа в разработке, быстро учусь.",
    },
    {
        "email": "sergey.volkov@demo.ru",
        "name": "Сергей Волков",
        "specialization": "frontend",
        "grade": "middle",
        "theta": 0.5,
        "years": 5,
        "fsp_id": None,
        "stack": ["JavaScript", "TypeScript", "React", "Vue"],
        "summary": "Собираю интерфейсы и дизайн-системы.",
    },
    {
        "email": "marina.orlova@demo.ru",
        "name": "Марина Орлова",
        "specialization": "frontend",
        "grade": "senior",
        "theta": 1.2,
        "years": 8,
        "fsp_id": "fsp-1002",
        "stack": ["TypeScript", "React", "Node.js", "Docker"],
        "summary": "Фронтенд-архитектор, менторю команду из пяти человек.",
    },
    {
        "email": "ivan.lebdev@demo.ru",
        "name": "Иван Лебедев",
        "specialization": "devops",
        "grade": "middle",
        "theta": 0.7,
        "years": 5,
        "fsp_id": None,
        "stack": ["Linux", "Docker", "Kubernetes", "Git", "Redis"],
        "summary": "Автоматизирую деплой и мониторинг.",
    },
    {
        "email": "elena.fedorova@demo.ru",
        "name": "Елена Фёдорова",
        "specialization": "qa",
        "grade": "middle",
        "theta": 0.4,
        "years": 4,
        "fsp_id": None,
        "stack": ["SQL", "Git", "Linux"],
        "summary": "Тестирую API и пишу автотесты.",
    },
    {
        "email": "pavel.morozov@demo.ru",
        "name": "Павел Морозов",
        "specialization": "analyst",
        "grade": "junior_plus",
        "theta": -0.3,
        "years": 2,
        "fsp_id": None,
        "stack": ["SQL", "Python"],
        "summary": "Пишу ТЗ и схемы интеграций.",
    },
]

DEMO_EMPLOYERS: list[dict[str, Any]] = [
    {
        "email": "hr@fintech-demo.ru",
        "company": "ООО «ФинТех Решения»",
        "description": "Разрабатываем платёжные сервисы и внутренние системы банка.",
        "website": "https://fintech-demo.ru",
    },
    {
        "email": "hr@digital-demo.ru",
        "company": "«Диджитал Продукт»",
        "description": "Продуктовая IT-компания: маркетплейс и логистика.",
        "website": "https://digital-demo.ru",
    },
]


async def _seed_interactions(session: AsyncSession, specializations: dict[str, int]) -> int:
    """Создаёт потребности и приглашения с разными статусами.

    Нужно для демонстрации: кабинет администратора наблюдает за взаимодействием
    сторон, а разделы работодателя и кандидата выглядят живыми. Статусы намеренно
    разные — на них видно и воронку, и ликвидность рынка.
    """
    from app.schemas.employer import NeedIn
    from app.schemas.invitation import InvitationCreate
    from app.services import employers as employer_service
    from app.services import invitations as invitation_service
    from app.services import reference

    plans = [
        {
            "employer": "hr@fintech-demo.ru",
            "title": "Backend-разработчик (Python)",
            "specialization": "backend",
            "grade": "middle",
            "stack": ["Python", "PostgreSQL", "Docker"],
            "salary": (250000, 320000),
            # (сколько кандидатов пригласить, действия по порядку)
            "actions": ["accepted", "declined", "sent"],
        },
        {
            "employer": "hr@digital-demo.ru",
            "title": "Frontend-разработчик (React)",
            "specialization": "frontend",
            "grade": "senior",
            "stack": ["React", "TypeScript"],
            "salary": (300000, 380000),
            "actions": ["viewed", "revoked", "sent"],
        },
    ]

    created = 0
    for plan in plans:
        employer = (
            await session.execute(select(User).where(User.email == plan["employer"]))
        ).scalar_one_or_none()
        if employer is None:
            continue
        if plan["specialization"] not in specializations:
            continue

        existing = (
            await session.execute(
                select(EmployerNeed).where(
                    EmployerNeed.employer_id == employer.id, EmployerNeed.title == plan["title"]
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue

        need = await employer_service.create_need(
            session,
            employer.id,
            NeedIn(
                title=plan["title"],
                description="Демонстрационная потребность для показа подбора.",
                specialization_code=plan["specialization"],
                grade=plan["grade"],
                stack=plan["stack"],
                salary_from=plan["salary"][0],
                salary_to=plan["salary"][1],
            ),
        )
        # Подборку строит отдельный шаг — так же, как это делает API при описании потребности
        selection, _ = await employer_service.build_selection(session, employer.id, need)
        if selection is None:
            continue

        in_selection = {
            row.candidate_user_id
            for row in (
                await session.execute(
                    select(SelectionCandidate).where(SelectionCandidate.selection_id == selection.id)
                )
            )
            .scalars()
            .all()
        }
        all_candidates = (
            (await session.execute(select(User).where(User.role == UserRole.CANDIDATE))).scalars().all()
        )
        # Приглашаем именно из подборки: это и есть реальный путь работодателя.
        candidates = [user for user in all_candidates if user.id in in_selection]
        if not candidates:
            candidates = list(all_candidates)
        for user, action in zip(candidates, plan["actions"], strict=False):
            invitation = await invitation_service.create_invitation(
                session,
                employer.id,
                InvitationCreate(
                    candidate_reference=reference.candidate_reference(user.id),
                    message="Демонстрационное приглашение: расскажем о команде и задачах.",
                    salary_from=plan["salary"][0],
                    salary_to=plan["salary"][1],
                    contact_method="hr@demo.ru",
                    need_id=need.id,
                    selection_id=selection.id,
                ),
            )
            created += 1
            if action == "accepted":
                await invitation_service.decide(session, user.id, invitation.id, accept=True)
            elif action == "declined":
                await invitation_service.decide(session, user.id, invitation.id, accept=False)
            elif action == "viewed":
                await invitation_service.mark_viewed(session, user.id, invitation.id)
            elif action == "revoked":
                await invitation_service.revoke(session, employer.id, invitation.id)
    return created


async def _seed_vacancies(session: AsyncSession, specializations: dict[str, int]) -> int:
    """Публикует вакансии компаний.

    Нужны для демонстрации: у вакансий вторая механика — кандидат откликается сам,
    и тогда контакты раскрываются сразу. По опубликованным вакансиям строятся и
    подсказки соискателю: без них раздел выглядел бы пустым.
    """
    from app.services import marketplace

    plans = [
        {
            "employer": "hr@fintech-demo.ru",
            "title": "Python-разработчик в платёжный сервис",
            "specialization": "backend",
            "grade": "middle",
            "stack": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "salary": (220000, 300000),
            "description": (
                "Развиваем платёжный сервис: обработка платежей, интеграции с банками, "
                "надёжность под нагрузкой. Ищем разработчика в команду из шести человек."
            ),
        },
        {
            "employer": "hr@digital-demo.ru",
            "title": "Frontend-разработчик (React)",
            "specialization": "frontend",
            "grade": "senior",
            "stack": ["React", "TypeScript", "Vite"],
            "salary": (280000, 360000),
            "description": (
                "Продуктовая команда делает интерфейсы личного кабинета для крупного "
                "клиента. Нужен человек, который отвечает за качество интерфейса целиком."
            ),
        },
        {
            "employer": "hr@fintech-demo.ru",
            "title": "DevOps-инженер",
            "specialization": "devops",
            "grade": "middle",
            "stack": ["Docker", "Kubernetes", "CI/CD"],
            "salary": (240000, 320000),
            "description": (
                "Поддерживаем и развиваем инфраструктуру сервисов: сборки, окружения, "
                "наблюдаемость. Работа рядом с командами разработки."
            ),
        },
    ]

    created = 0
    for plan in plans:
        if plan["specialization"] not in specializations:
            continue
        employer = (
            await session.execute(select(User).where(User.email == plan["employer"]))
        ).scalar_one_or_none()
        if employer is None:
            continue
        existing = (
            await session.execute(
                select(Vacancy).where(Vacancy.employer_id == employer.id, Vacancy.title == plan["title"])
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        await marketplace.create_vacancy(
            session,
            employer.id,
            {
                "title": plan["title"],
                "description": plan["description"],
                "specialization_code": plan["specialization"],
                "grade": plan["grade"],
                "stack": plan["stack"],
                "salary_from": plan["salary"][0],
                "salary_to": plan["salary"][1],
            },
        )
        created += 1
    return created


async def seed() -> dict[str, int]:
    factory = get_session_factory()
    created = {"candidates": 0, "employers": 0, "sessions": 0}

    async with factory() as session:
        await ensure_reference_data(session)
        rows = (await session.execute(select(Specialization.code, Specialization.id))).all()
        specializations = dict(rows)

        for candidate in DEMO_CANDIDATES:
            exists = (
                await session.execute(select(User).where(User.email == candidate["email"]))
            ).scalar_one_or_none()
            if exists is not None:
                continue

            user = User(
                email=candidate["email"],
                password_hash=hash_password(DEMO_PASSWORD),
                role=UserRole.CANDIDATE,
                email_verified=True,
                is_active=True,
                fsp_id=candidate.get("fsp_id"),
                consent_pdn_at=utcnow(),
                consent_pdn_version="pdn-v1",
                consent_publish_at=utcnow(),
            )
            session.add(user)
            await session.flush()
            created["candidates"] += 1

            session.add(
                CandidateProfile(
                    user_id=user.id,
                    full_name=candidate["name"],
                    contacts={"email": candidate["email"], "phone": "+7 900 000-00-00", "telegram": "@demo"},
                    specialization=candidate["specialization"],
                    grade=candidate["grade"],
                    experience_years=candidate["years"],
                    stack=list(candidate["stack"]),
                    roles=[candidate["specialization"]],
                    soft_skills=["командная работа"],
                    summary=candidate["summary"],
                    resume_source="form",
                )
            )

            session.add(
                TestSession(
                    user_id=user.id,
                    specialization_id=specializations[candidate["specialization"]],
                    target_grade=candidate["grade"],
                    status=SESSION_COMPLETED,
                    item_count=9,
                    theta=candidate["theta"],
                    standard_error=0.35,
                    result_grade=candidate["grade"],
                    finished_at=utcnow(),
                )
            )
            created["sessions"] += 1

        for employer in DEMO_EMPLOYERS:
            exists = (
                await session.execute(select(User).where(User.email == employer["email"]))
            ).scalar_one_or_none()
            if exists is not None:
                continue
            user = User(
                email=employer["email"],
                password_hash=hash_password(DEMO_PASSWORD),
                role=UserRole.EMPLOYER,
                email_verified=True,
                is_active=True,
                consent_pdn_at=utcnow(),
                consent_pdn_version="pdn-v1",
            )
            session.add(user)
            await session.flush()
            session.add(
                EmployerProfile(
                    user_id=user.id,
                    company_name=employer["company"],
                    description=employer["description"],
                    industry="it",
                    website=employer["website"],
                    contact_email=employer["email"],
                )
            )
            created["employers"] += 1

        # Администратор: роль не саморегистрируемая, поэтому создаётся только здесь.
        admin_exists = (
            await session.execute(select(User).where(User.email == DEMO_ADMIN_EMAIL))
        ).scalar_one_or_none()
        if admin_exists is None:
            session.add(
                User(
                    email=DEMO_ADMIN_EMAIL,
                    password_hash=hash_password(DEMO_PASSWORD),
                    role=UserRole.ADMIN,
                    email_verified=True,
                    is_active=True,
                    consent_pdn_at=utcnow(),
                    consent_pdn_version="pdn-v1",
                )
            )
            created["admins"] = 1

        await session.flush()

        # Демонстрационные взаимодействия: без них кабинет администратора показывал бы
        # пустые графики, а жюри не увидело бы основную механику — приглашение.
        created["invitations"] = await _seed_interactions(session, specializations)
        # Опубликованные вакансии: вторая механика (кандидат откликается сам) и вход
        # для подсказок вакансий — без них у соискателя нечего было бы подсказывать.
        created["vacancies"] = await _seed_vacancies(session, specializations)

        await session.commit()

    await dispose_engine()
    return created


if __name__ == "__main__":
    result = asyncio.run(seed())
    print(f"демо-данные: {result}")
    print(f"пароль демо-пользователей: {DEMO_PASSWORD}")
