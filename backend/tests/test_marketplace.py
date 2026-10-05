"""Тесты дополнительного функционала: вакансии, отклики, регулярные задания."""

from __future__ import annotations

from datetime import timedelta
from typing import Dict, Optional

from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import utcnow
from app.models.candidate import CandidateProfile
from app.models.testing import SESSION_COMPLETED, TestSession as SessionRow
from app.models.user import User
from app.services import marketplace as market
from tests.conftest import register_and_verify

CANDIDATE_CONTACTS = {
    "email": "applier@example.com",
    "phone": "+7 911 222-33-44",
    "telegram": "@applier",
}


async def _login_only(client: AsyncClient, email: str, password: str = "secret12345") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _register_login(client: AsyncClient, email: str, role: str) -> str:
    await register_and_verify(client, email, role=role)
    return await _login_only(client, email)


def _auth(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _candidate(client: AsyncClient, db_factory, email: str,
                     contacts: Optional[Dict[str, str]] = None) -> str:
    await register_and_verify(client, email)
    async with db_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.add(CandidateProfile(
            user_id=user.id,
            full_name="Откликнувшийся Кандидат",
            contacts=dict(contacts if contacts is not None else CANDIDATE_CONTACTS),
            specialization="backend",
            grade="middle",
            experience_years=3,
            stack=["Python", "Docker"],
            roles=["backend"],
        ))
        session.add(SessionRow(
            user_id=user.id, specialization_id=1, target_grade="middle",
            status=SESSION_COMPLETED, item_count=8, theta=0.5, standard_error=0.4,
            result_grade="middle",
        ))
        await session.commit()
        return user.id


async def _employer(client: AsyncClient, email: str) -> str:
    token = await _register_login(client, email, "employer")
    await client.put(
        "/api/v1/employers/me/profile",
        json={"company_name": "ООО «Доп. функционал»"}, headers=_auth(token),
    )
    return token


async def _vacancy(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {
        "title": "Backend-разработчик",
        "description": "Команда платежей",
        "specialization_code": "backend",
        "grade": "middle",
        "stack": ["Python", "Docker"],
        "salary_from": 250000,
        "salary_to": 320000,
        **overrides,
    }
    response = await client.post("/api/v1/employers/me/vacancies", json=payload,
                                 headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()


# --- Вакансии ------------------------------------------------------------------

async def test_vacancy_requires_employer_role(client: AsyncClient) -> None:
    token = await _register_login(client, "cand-vac@example.com", "candidate")
    response = await client.post(
        "/api/v1/employers/me/vacancies",
        json={"title": "Тест", "salary_from": 1, "salary_to": 2}, headers=_auth(token),
    )
    assert response.status_code == 403


async def test_vacancy_salary_range_validated(client: AsyncClient) -> None:
    token = await _employer(client, "vac-validate@example.com")
    response = await client.post(
        "/api/v1/employers/me/vacancies",
        json={"title": "Тест", "salary_from": 500000, "salary_to": 100000}, headers=_auth(token),
    )
    assert response.status_code == 400


async def test_vacancy_grade_and_specialization_validated(client: AsyncClient) -> None:
    token = await _employer(client, "vac-validate2@example.com")
    assert (await client.post(
        "/api/v1/employers/me/vacancies",
        json={"title": "Тест", "grade": "godlike", "salary_from": 1, "salary_to": 2},
        headers=_auth(token),
    )).status_code == 400
    assert (await client.post(
        "/api/v1/employers/me/vacancies",
        json={"title": "Тест", "specialization_code": "no-such", "salary_from": 1, "salary_to": 2},
        headers=_auth(token),
    )).status_code == 404


async def test_candidate_sees_open_vacancies_only(client: AsyncClient, db_factory) -> None:
    employer = await _employer(client, "vac-list@example.com")
    vacancy = await _vacancy(client, employer)
    candidate = await _register_login(client, "vac-see@example.com", "candidate")

    open_list = await client.get("/api/v1/candidates/me/vacancies", headers=_auth(candidate))
    assert open_list.status_code == 200
    assert any(v["id"] == vacancy["id"] for v in open_list.json())
    assert open_list.json()[0]["company_name"] == "ООО «Доп. функционал»"
    assert open_list.json()[0]["salary_from"] == 250000

    await client.post(f"/api/v1/employers/me/vacancies/{vacancy['id']}/close",
                      headers=_auth(employer))
    after_close = await client.get("/api/v1/candidates/me/vacancies", headers=_auth(candidate))
    assert all(v["id"] != vacancy["id"] for v in after_close.json())


# --- Отклики -------------------------------------------------------------------

async def test_application_reveals_contacts_to_employer(client: AsyncClient, db_factory) -> None:
    candidate_id = await _candidate(client, db_factory, "applier@example.com")
    candidate_token = await _login_only(client, "applier@example.com")
    employer_token = await _employer(client, "app-emp@example.com")
    vacancy = await _vacancy(client, employer_token)

    applied = await client.post(
        f"/api/v1/candidates/me/vacancies/{vacancy['id']}/applications",
        json={"message": "Хочу в команду"}, headers=_auth(candidate_token),
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "sent"
    assert applied.json()["company_name"] == "ООО «Доп. функционал»"

    applications = await client.get(
        f"/api/v1/employers/me/vacancies/{vacancy['id']}/applications",
        headers=_auth(employer_token),
    )
    assert applications.status_code == 200
    item = applications.json()[0]
    assert item["candidate_reference"] == f"cand-{candidate_id[:8]}"
    # Кандидат откликнулся сам — контакты открыты
    assert item["contacts_revealed"] is True
    assert item["candidate_contacts"]["email"] == "applier@example.com"
    assert item["candidate_contacts"]["phone"] == "+7 911 222-33-44"


async def test_duplicate_application_rejected(client: AsyncClient, db_factory) -> None:
    await _candidate(client, db_factory, "dup-app@example.com")
    token = await _login_only(client, "dup-app@example.com")
    employer_token = await _employer(client, "dup-app-emp@example.com")
    vacancy = await _vacancy(client, employer_token)

    url = f"/api/v1/candidates/me/vacancies/{vacancy['id']}/applications"
    assert (await client.post(url, json={}, headers=_auth(token))).status_code == 200
    assert (await client.post(url, json={}, headers=_auth(token))).status_code == 409


async def test_application_to_closed_vacancy_rejected(client: AsyncClient, db_factory) -> None:
    await _candidate(client, db_factory, "closed-app@example.com")
    token = await _login_only(client, "closed-app@example.com")
    employer_token = await _employer(client, "closed-app-emp@example.com")
    vacancy = await _vacancy(client, employer_token)
    await client.post(f"/api/v1/employers/me/vacancies/{vacancy['id']}/close",
                      headers=_auth(employer_token))

    response = await client.post(
        f"/api/v1/candidates/me/vacancies/{vacancy['id']}/applications",
        json={}, headers=_auth(token),
    )
    assert response.status_code == 409


async def test_employer_decides_on_application(client: AsyncClient, db_factory) -> None:
    await _candidate(client, db_factory, "decide-app@example.com")
    token = await _login_only(client, "decide-app@example.com")
    employer_token = await _employer(client, "decide-app-emp@example.com")
    vacancy = await _vacancy(client, employer_token)

    applied = await client.post(
        f"/api/v1/candidates/me/vacancies/{vacancy['id']}/applications",
        json={}, headers=_auth(token),
    )
    application_id = applied.json()["id"]

    decided = await client.post(
        f"/api/v1/employers/me/vacancies/applications/{application_id}/decision",
        json={"status": "accepted"}, headers=_auth(employer_token),
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "accepted"

    again = await client.post(
        f"/api/v1/employers/me/vacancies/applications/{application_id}/decision",
        json={"status": "declined"}, headers=_auth(employer_token),
    )
    assert again.status_code == 409

    mine = await client.get("/api/v1/candidates/me/applications", headers=_auth(token))
    assert mine.json()[0]["status"] == "accepted"
    assert mine.json()[0]["vacancy_title"] == "Backend-разработчик"


async def test_employer_cannot_read_foreign_vacancy_applications(
    client: AsyncClient, db_factory
) -> None:
    await _candidate(client, db_factory, "foreign-app@example.com")
    owner = await _employer(client, "foreign-owner@example.com")
    stranger = await _employer(client, "foreign-stranger@example.com")
    vacancy = await _vacancy(client, owner)

    response = await client.get(
        f"/api/v1/employers/me/vacancies/{vacancy['id']}/applications",
        headers=_auth(stranger),
    )
    assert response.status_code == 404


async def test_candidate_cannot_see_other_applications(client: AsyncClient, db_factory) -> None:
    await _candidate(client, db_factory, "owner-app@example.com")
    await _candidate(client, db_factory, "other-app@example.com")
    owner_token = await _login_only(client, "owner-app@example.com")
    other_token = await _login_only(client, "other-app@example.com")
    employer_token = await _employer(client, "apps-iso@example.com")
    vacancy = await _vacancy(client, employer_token)

    await client.post(f"/api/v1/candidates/me/vacancies/{vacancy['id']}/applications",
                      json={}, headers=_auth(owner_token))

    assert (await client.get("/api/v1/candidates/me/applications",
                             headers=_auth(other_token))).json() == []


# --- Регулярные короткие задания ----------------------------------------------

async def test_task_lifecycle(client: AsyncClient, db_factory) -> None:
    await _candidate(client, db_factory, "tasker@example.com")
    candidate_token = await _login_only(client, "tasker@example.com")
    employer_token = await _employer(client, "task-emp@example.com")

    created = await client.post(
        "/api/v1/employers/me/tasks",
        json={"title": "Спроектируйте идемпотентный вебхук",
              "description": "Опишите подход или приведите код",
              "specialization_code": "backend", "grade": "middle"},
        headers=_auth(employer_token),
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    offered = await client.get("/api/v1/candidates/me/tasks", headers=_auth(candidate_token))
    assert offered.status_code == 200
    assert any(t["id"] == task_id for t in offered.json())

    submitted = await client.post(
        f"/api/v1/candidates/me/tasks/{task_id}/submissions",
        json={"solution": "Использую ключ идемпотентности в заголовке и хранилище ключей."},
        headers=_auth(candidate_token),
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    empty = await client.post(
        f"/api/v1/candidates/me/tasks/{task_id}/submissions",
        json={"solution": "   "}, headers=_auth(candidate_token),
    )
    # Строка из пробелов проходит схему, но отклоняется сервисом с понятным сообщением
    assert empty.status_code == 400
    assert "пустым" in empty.json()["detail"]

    submissions = await client.get(
        f"/api/v1/employers/me/tasks/{task_id}/submissions", headers=_auth(employer_token)
    )
    assert submissions.status_code == 200
    assert len(submissions.json()) == 1
    assert submissions.json()[0]["candidate_grade"] == "middle"


async def test_task_submission_refreshes_profile_activity(
    client: AsyncClient, db_factory
) -> None:
    """Участие в коротких заданиях даёт работодателю свежий сигнал о кандидате."""
    email = "freshness@example.com"
    await register_and_verify(client, email)
    long_ago = utcnow() - timedelta(days=200)

    async with db_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.add(CandidateProfile(
            user_id=user.id, full_name="Давний Кандидат", contacts={},
            specialization="backend", grade="middle", stack=["Python"],
        ))
        session.add(SessionRow(
            user_id=user.id, specialization_id=1, target_grade="middle",
            status=SESSION_COMPLETED, item_count=8, theta=0.5, standard_error=0.4,
            result_grade="middle", started_at=long_ago, finished_at=long_ago,
        ))
        await session.commit()

        before = await market.last_activity_at(session, user.id)
        assert before is not None and (utcnow() - before).days > 100

    token = await _login_only(client, email)
    employer_token = await _employer(client, "freshness-emp@example.com")
    task = await client.post(
        "/api/v1/employers/me/tasks",
        json={"title": "Короткая задача", "specialization_code": "backend"},
        headers=_auth(employer_token),
    )
    await client.post(
        f"/api/v1/candidates/me/tasks/{task.json()['id']}/submissions",
        json={"solution": "Подход описан"}, headers=_auth(token),
    )

    async with db_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        after = await market.last_activity_at(session, user.id)
        assert after is not None and (utcnow() - after).days == 0
