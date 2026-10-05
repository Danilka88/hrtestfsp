"""Тесты подсказок: близкие вакансии кандидату и кандидаты работодателю.

Проверяется, что подсказки опираются на действия пользователя, объяснимы (у каждой
позиции есть причина), не предлагают уже использованное и не ломают основной путь.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.candidate import CandidateProfile
from app.models.testing import SESSION_COMPLETED
from app.models.testing import TestSession as SessionRow
from app.models.user import User
from tests.conftest import register_and_verify


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str, password: str = "secret12345") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _make_candidate(
    client: AsyncClient,
    db_factory,
    email: str,
    *,
    specialization: str = "backend",
    grade: str = "middle",
    stack: list[str] | None = None,
) -> str:
    await register_and_verify(client, email)
    async with db_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.add(
            CandidateProfile(
                user_id=user.id,
                full_name="Кандидат Подсказок",
                contacts={"email": email},
                specialization=specialization,
                grade=grade,
                experience_years=4,
                stack=stack or ["Python", "Docker"],
                roles=["backend"],
                summary="Пишу сервисы на Python, работаю с PostgreSQL и Docker",
            )
        )
        session.add(
            SessionRow(
                user_id=user.id,
                specialization_id=1,
                target_grade=grade,
                status=SESSION_COMPLETED,
                item_count=8,
                theta=0.6,
            )
        )
        await session.commit()
        return user.id


async def _make_vacancy(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {
        "title": "Backend-разработчик",
        "description": "Команда платежей, Python и PostgreSQL",
        "specialization_code": "backend",
        "grade": "middle",
        "stack": ["Python", "PostgreSQL"],
        "salary_from": 250000,
        "salary_to": 320000,
        **overrides,
    }
    response = await client.post("/api/v1/employers/me/vacancies", json=payload, headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()


# --- Кандидат: близкие вакансии -------------------------------------------------


async def test_vacancy_hints_require_candidate_role(client: AsyncClient, db_factory) -> None:
    await register_and_verify(client, "hint-emp@example.com", role="employer")
    token = await _login(client, "hint-emp@example.com")
    assert (await client.get("/api/v1/ai/candidate/vacancy-hints", headers=_auth(token))).status_code == 403


async def test_vacancy_hints_without_vacancies_explain_emptiness(client: AsyncClient, db_factory) -> None:
    """Пустая выдача — с пояснением, а не молчаливым пустым списком."""
    await _make_candidate(client, db_factory, "hint-cand-empty@example.com")
    token = await _login(client, "hint-cand-empty@example.com")

    body = (await client.get("/api/v1/ai/candidate/vacancy-hints", headers=_auth(token))).json()
    assert body["items"] == []
    assert body["note"]
    assert body["anchor"] == "none"


async def test_vacancy_hints_rank_by_profile_and_explain(client: AsyncClient, db_factory) -> None:
    employer = await register_and_verify(client, "hint-emp2@example.com", role="employer")
    assert employer["role"] == "employer"
    emp_token = await _login(client, "hint-emp2@example.com")
    await _make_vacancy(client, emp_token, title="Backend Python", stack=["Python", "PostgreSQL"])
    await _make_vacancy(
        client,
        emp_token,
        title="Фронтенд React",
        specialization_code="frontend",
        grade="senior",
        stack=["React", "TypeScript"],
    )

    await _make_candidate(client, db_factory, "hint-cand@example.com")
    token = await _login(client, "hint-cand@example.com")

    body = (await client.get("/api/v1/ai/candidate/vacancy-hints", headers=_auth(token))).json()
    items = body["items"]
    assert len(items) == 2
    # Профиль backend/middle — профильная вакансия должна быть выше
    assert items[0]["title"] == "Backend Python"
    assert items[0]["score"] > items[1]["score"]
    # Каждая позиция объяснена
    assert items[0]["reasons"] and all(isinstance(reason, str) for reason in items[0]["reasons"])
    assert any("грейд" in reason or "стек" in reason for reason in items[0]["reasons"])


async def test_vacancy_hints_anchor_on_chosen_vacancies(client: AsyncClient, db_factory) -> None:
    """Если кандидат выбирал вакансии, подсказки опираются на них и не повторяют их."""
    await register_and_verify(client, "hint-emp3@example.com", role="employer")
    emp_token = await _login(client, "hint-emp3@example.com")
    chosen = await _make_vacancy(client, emp_token, title="Выбранная вакансия")
    await _make_vacancy(client, emp_token, title="Похожая вакансия")
    await _make_vacancy(
        client, emp_token, title="Далекая вакансия", specialization_code="frontend", grade="senior"
    )

    await _make_candidate(client, db_factory, "hint-cand3@example.com")
    token = await _login(client, "hint-cand3@example.com")
    applied = await client.post(
        f"/api/v1/candidates/me/vacancies/{chosen['id']}/applications",
        json={"message": "Интересно"},
        headers=_auth(token),
    )
    assert applied.status_code == 200, applied.text

    body = (await client.get("/api/v1/ai/candidate/vacancy-hints", headers=_auth(token))).json()
    titles = [item["title"] for item in body["items"]]
    assert "Выбранная вакансия" not in titles  # уже откликнулся — повторять незачем
    assert "Похожая вакансия" in titles
    assert body["anchor"] == "applications"


# --- Работодатель: кандидаты ---------------------------------------------------


async def test_candidate_hints_require_employer_role(client: AsyncClient, db_factory) -> None:
    await _make_candidate(client, db_factory, "hint-cand-role@example.com")
    token = await _login(client, "hint-cand-role@example.com")
    assert (await client.get("/api/v1/ai/employer/candidate-hints", headers=_auth(token))).status_code == 403


async def test_candidate_hints_without_actions_explain_emptiness(client: AsyncClient, db_factory) -> None:
    await register_and_verify(client, "hint-idle-emp@example.com", role="employer")
    token = await _login(client, "hint-idle-emp@example.com")

    body = (await client.get("/api/v1/ai/employer/candidate-hints", headers=_auth(token))).json()
    assert body["items"] == []
    assert body["anchor"] == "none"
    assert "действий" in body["note"]


async def test_candidate_hints_follow_employer_need(client: AsyncClient, db_factory) -> None:
    await _make_candidate(client, db_factory, "hint-back@example.com", specialization="backend")
    await _make_candidate(
        client,
        db_factory,
        "hint-front@example.com",
        specialization="frontend",
        grade="senior",
        stack=["React", "TypeScript"],
    )

    await register_and_verify(client, "hint-need-emp@example.com", role="employer")
    token = await _login(client, "hint-need-emp@example.com")
    need = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Backend", "specialization_code": "backend", "grade": "middle"},
        headers=_auth(token),
    )
    assert need.status_code == 200, need.text

    body = (await client.get("/api/v1/ai/employer/candidate-hints", headers=_auth(token))).json()
    items = body["items"]
    assert items, body
    # Первым должен идти кандидат из категории потребности
    assert items[0]["specialization"] == "backend"
    assert items[0]["reference"].startswith("cand-")
    assert items[0]["reasons"]
    assert any("категория" in reason or "специализация" in reason for reason in items[0]["reasons"])


async def test_candidate_hints_skip_already_invited(client: AsyncClient, db_factory) -> None:
    """Уже приглашённых повторно не подсказываем — это была бы ручная работа впустую."""
    await _make_candidate(client, db_factory, "hint-invited@example.com", specialization="backend")
    await _make_candidate(
        client, db_factory, "hint-other@example.com", specialization="backend", stack=["Python"]
    )

    await register_and_verify(client, "hint-invite-emp@example.com", role="employer")
    token = await _login(client, "hint-invite-emp@example.com")
    need = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Backend", "specialization_code": "backend", "grade": "middle"},
        headers=_auth(token),
    )
    reference = need.json()["candidates"][0]["reference"]

    sent = await client.post(
        "/api/v1/employers/me/invitations",
        json={
            "candidate_reference": reference,
            "message": "Приглашаем",
            "salary_from": 250000,
            "salary_to": 300000,
        },
        headers=_auth(token),
    )
    assert sent.status_code == 200, sent.text

    body = (await client.get("/api/v1/ai/employer/candidate-hints", headers=_auth(token))).json()
    references = [item["reference"] for item in body["items"]]
    assert reference not in references
