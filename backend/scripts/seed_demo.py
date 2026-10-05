"""Демонстрационные данные для стенда.

Создаёт кандидатов с определёнными категориями (в том числе профиль без истории
ФСП) и работодателей. Идемпотентно: повторный запуск не дублирует записи.

Запуск в контейнере: docker compose exec -T backend python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List

# Позволяет запускать скрипт и как `python scripts/seed_demo.py`, и как `python -m scripts.seed_demo`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.security import hash_password, utcnow
from app.db.session import dispose_engine, get_session_factory
from app.models.candidate import CandidateProfile
from app.models.employer import EmployerProfile
from app.models.testing import SESSION_COMPLETED, Specialization, TestSession
from app.models.user import User, UserRole
from app.services.reference import ensure_reference_data

DEMO_PASSWORD = "demo12345"

DEMO_CANDIDATES: List[Dict[str, Any]] = [
    {"email": "anna.kovaleva@demo.ru", "name": "Анна Ковалёва", "specialization": "backend",
     "grade": "senior", "theta": 1.4, "years": 7, "fsp_id": "fsp-1001",
     "stack": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Redis"],
     "summary": "Проектирую высоконагруженные сервисы, наставник в команде."},
    {"email": "dmitry.sokolov@demo.ru", "name": "Дмитрий Соколов", "specialization": "backend",
     "grade": "middle", "theta": 0.6, "years": 4, "fsp_id": None,
     "stack": ["Python", "Django", "PostgreSQL", "Docker", "Kafka"],
     "summary": "Разрабатываю внутренние сервисы, люблю аккуратные миграции."},
    {"email": "olga.nikolaeva@demo.ru", "name": "Ольга Николаева", "specialization": "backend",
     "grade": "junior", "theta": -0.7, "years": 1, "fsp_id": "fsp-2000",
     "stack": ["Python", "Flask", "SQL", "Git"],
     "summary": "Первая работа в разработке, быстро учусь."},
    {"email": "sergey.volkov@demo.ru", "name": "Сергей Волков", "specialization": "frontend",
     "grade": "middle", "theta": 0.5, "years": 5, "fsp_id": None,
     "stack": ["JavaScript", "TypeScript", "React", "Vue"],
     "summary": "Собираю интерфейсы и дизайн-системы."},
    {"email": "marina.orlova@demo.ru", "name": "Марина Орлова", "specialization": "frontend",
     "grade": "senior", "theta": 1.2, "years": 8, "fsp_id": "fsp-1002",
     "stack": ["TypeScript", "React", "Node.js", "Docker"],
     "summary": "Фронтенд-архитектор, менторю команду из пяти человек."},
    {"email": "ivan.lebdev@demo.ru", "name": "Иван Лебедев", "specialization": "devops",
     "grade": "middle", "theta": 0.7, "years": 5, "fsp_id": None,
     "stack": ["Linux", "Docker", "Kubernetes", "Git", "Redis"],
     "summary": "Автоматизирую деплой и мониторинг."},
    {"email": "elena.fedorova@demo.ru", "name": "Елена Фёдорова", "specialization": "qa",
     "grade": "middle", "theta": 0.4, "years": 4, "fsp_id": None,
     "stack": ["SQL", "Git", "Linux"],
     "summary": "Тестирую API и пишу автотесты."},
    {"email": "pavel.morozov@demo.ru", "name": "Павел Морозов", "specialization": "analyst",
     "grade": "junior_plus", "theta": -0.3, "years": 2, "fsp_id": None,
     "stack": ["SQL", "Python"],
     "summary": "Пишу ТЗ и схемы интеграций."},
]

DEMO_EMPLOYERS: List[Dict[str, Any]] = [
    {"email": "hr@fintech-demo.ru", "company": "ООО «ФинТех Решения»",
     "description": "Разрабатываем платёжные сервисы и внутренние системы банка.",
     "website": "https://fintech-demo.ru"},
    {"email": "hr@digital-demo.ru", "company": "«Диджитал Продукт»",
     "description": "Продуктовая IT-компания: маркетплейс и логистика.",
     "website": "https://digital-demo.ru"},
]


async def seed() -> Dict[str, int]:
    factory = get_session_factory()
    created = {"candidates": 0, "employers": 0, "sessions": 0}

    async with factory() as session:
        await ensure_reference_data(session)
        specializations = {
            code: ident for code, ident in
            (await session.execute(select(Specialization.code, Specialization.id))).all()
        }

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

            session.add(CandidateProfile(
                user_id=user.id,
                full_name=candidate["name"],
                contacts={"email": candidate["email"], "phone": "+7 900 000-00-00",
                          "telegram": "@demo"},
                specialization=candidate["specialization"],
                grade=candidate["grade"],
                experience_years=candidate["years"],
                stack=list(candidate["stack"]),
                roles=[candidate["specialization"]],
                soft_skills=["командная работа"],
                summary=candidate["summary"],
                resume_source="form",
            ))

            session.add(TestSession(
                user_id=user.id,
                specialization_id=specializations[candidate["specialization"]],
                target_grade=candidate["grade"],
                status=SESSION_COMPLETED,
                item_count=9,
                theta=candidate["theta"],
                standard_error=0.35,
                result_grade=candidate["grade"],
                finished_at=utcnow(),
            ))
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
            session.add(EmployerProfile(
                user_id=user.id,
                company_name=employer["company"],
                description=employer["description"],
                industry="it",
                website=employer["website"],
                contact_email=employer["email"],
            ))
            created["employers"] += 1

        await session.commit()

    await dispose_engine()
    return created


if __name__ == "__main__":
    result = asyncio.run(seed())
    print(f"демо-данные: {result}")
    print(f"пароль демо-пользователей: {DEMO_PASSWORD}")
