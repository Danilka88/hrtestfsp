"""Тесты кабинета работодателя: подборка, ранжирование, объяснимость, поиск."""

from __future__ import annotations

import json

from httpx import AsyncClient
from sqlalchemy import select

from app.models.candidate import CandidateProfile
from app.models.user import User
from app.services.fit import compute_fit, normalize_theta, stack_overlap
from app.services.matching import WEIGHTS, CandidateSignals, score_candidate
from app.services.testing import GRADE_ORDER
from tests.conftest import register_and_verify

# --- Юнит-уровень: сигналы и мера соответствия -------------------------------


def test_normalize_theta_is_monotonic_and_bounded() -> None:
    low = normalize_theta(-4.0)
    mid = normalize_theta(0.0)
    high = normalize_theta(4.0)
    assert low is not None and mid is not None and high is not None
    assert low < mid < high
    assert all(0.0 <= value <= 1.0 for value in (low, mid, high))
    assert normalize_theta(None) is None


def test_stack_overlap() -> None:
    assert stack_overlap(["Python", "Docker"], ["python", "docker", "sql"]) == 1.0
    assert stack_overlap(["Python", "Docker"], ["Python"]) == 0.5
    assert stack_overlap([], ["Python"]) == 0.0


def test_fit_is_none_without_requirements() -> None:
    assert (
        compute_fit(
            required_stack=[],
            candidate_stack=["Python"],
            required_specialization=None,
            candidate_specialization="backend",
            required_grade=None,
            candidate_grade="middle",
            grade_order=GRADE_ORDER,
        )
        is None
    )


def test_fit_penalises_grade_distance() -> None:
    close = compute_fit(
        required_stack=[],
        candidate_stack=[],
        required_specialization=None,
        candidate_specialization=None,
        required_grade="middle",
        candidate_grade="middle",
        grade_order=GRADE_ORDER,
    )
    far = compute_fit(
        required_stack=[],
        candidate_stack=[],
        required_specialization=None,
        candidate_specialization=None,
        required_grade="middle",
        candidate_grade="intern",
        grade_order=GRADE_ORDER,
    )
    assert close is not None and far is not None and close > far


def test_ranking_prefers_stronger_confirmed_profile() -> None:
    strong = score_candidate(
        CandidateSignals(
            candidate_id="strong",
            test_strength=0.9,
            fsp_achievements=2,
            days_since_last_task=5,
            semantic_fit=0.8,
        )
    )
    weak = score_candidate(
        CandidateSignals(
            candidate_id="weak",
            test_strength=0.3,
            fsp_achievements=0,
            days_since_last_task=150,
            semantic_fit=0.2,
        )
    )
    assert strong.score > weak.score
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


# --- Хелперы ------------------------------------------------------------------


async def _employer_token(client: AsyncClient, email: str) -> str:
    await register_and_verify(client, email, role="employer")
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "secret12345"})
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_candidate(
    client: AsyncClient,
    db_factory,
    *,
    email: str,
    specialization: str,
    grade: str,
    stack: list[str],
    theta: float = 0.5,
    fsp_id: str | None = None,
    privacy: dict[str, bool] | None = None,
) -> str:
    """Создаёт кандидата банка напрямую в БД (быстрее полного UI-пути)."""
    await register_and_verify(client, email)
    async with db_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        user.fsp_id = fsp_id
        profile = CandidateProfile(
            user_id=user.id,
            full_name=f"Кандидат {email.split('@')[0]}",
            contacts={"email": email, "phone": "+7 000 000-00-00", "telegram": "@secret"},
            specialization=specialization,
            grade=grade,
            experience_years=5,
            stack=stack,
            roles=[specialization],
            privacy=privacy or {},
        )
        session.add(profile)
        await session.flush()
        user_id = user.id

        # Завершённая сессия даёт «силу подтверждённого профиля»
        from app.models.testing import SESSION_COMPLETED, TestSession

        session.add(
            TestSession(
                user_id=user_id,
                specialization_id=1,
                target_grade=grade,
                status=SESSION_COMPLETED,
                item_count=8,
                theta=theta,
                standard_error=0.4,
                result_grade=grade,
            )
        )
        await session.commit()
    return user_id


async def _bank(client: AsyncClient, db_factory) -> dict[str, str]:
    ids = {}
    ids["strong"] = await _seed_candidate(
        client,
        db_factory,
        email="strong@bank.ru",
        specialization="backend",
        grade="middle",
        stack=["Python", "PostgreSQL", "Docker"],
        theta=1.2,
        fsp_id="fsp-1001",
    )
    ids["medium"] = await _seed_candidate(
        client,
        db_factory,
        email="medium@bank.ru",
        specialization="backend",
        grade="middle",
        stack=["Python", "Docker"],
        theta=0.2,
        fsp_id=None,
    )
    ids["junior"] = await _seed_candidate(
        client,
        db_factory,
        email="junior@bank.ru",
        specialization="backend",
        grade="junior",
        stack=["JavaScript", "React"],
        theta=-0.8,
        fsp_id="fsp-2000",
    )
    ids["frontend"] = await _seed_candidate(
        client,
        db_factory,
        email="frontend@bank.ru",
        specialization="frontend",
        grade="middle",
        stack=["JavaScript", "React", "TypeScript"],
        theta=1.0,
        fsp_id=None,
    )
    ids["hidden"] = await _seed_candidate(
        client,
        db_factory,
        email="hidden@bank.ru",
        specialization="backend",
        grade="middle",
        stack=["Python", "Kafka"],
        theta=0.9,
        fsp_id=None,
        privacy={"show_stack": False, "show_experience": False, "show_fsp": False},
    )
    return ids


# --- Профиль компании ---------------------------------------------------------


async def test_employer_profile_requires_employer_role(client: AsyncClient) -> None:
    await register_and_verify(client, "cand-not-emp@example.com")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "cand-not-emp@example.com", "password": "secret12345"}
    )
    token = login.json()["access_token"]
    assert (await client.get("/api/v1/employers/me/profile", headers=_auth(token))).status_code == 403


async def test_employer_profile_roundtrip(client: AsyncClient) -> None:
    token = await _employer_token(client, "company@example.com")
    assert (await client.get("/api/v1/employers/me/profile", headers=_auth(token))).status_code == 404

    created = await client.put(
        "/api/v1/employers/me/profile",
        json={
            "company_name": "ООО Ромашка",
            "description": "Разрабатываем финтех",
            "industry": "it",
            "contact_email": "hr@romashka.ru",
        },
        headers=_auth(token),
    )
    assert created.status_code == 200
    assert created.json()["company_name"] == "ООО Ромашка"

    fetched = await client.get("/api/v1/employers/me/profile", headers=_auth(token))
    assert fetched.json()["contact_email"] == "hr@romashka.ru"


# --- Подборка -----------------------------------------------------------------


async def test_need_creates_selection_ranked_by_confirmed_profile(client: AsyncClient, db_factory) -> None:
    ids = await _bank(client, db_factory)
    token = await _employer_token(client, "employer1@example.com")

    response = await client.post(
        "/api/v1/employers/me/needs",
        json={
            "title": "Backend-разработчик",
            "specialization_code": "backend",
            "grade": "middle",
            "stack": ["Python", "Docker"],
            "salary_from": 200000,
            "salary_to": 300000,
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    selection = response.json()
    assert selection["candidates"], "подборка не должна быть пустой"
    assert selection["recommended_categories"], "должны быть рекомендованные категории"

    cards = selection["candidates"]
    assert [c["rank"] for c in cards] == list(range(1, len(cards) + 1))
    scores = [c["score"] for c in cards]
    assert scores == sorted(scores, reverse=True), "подборка должна быть ранжирована"

    by_ref = {c["reference"]: c for c in cards}
    strong_ref = f"cand-{ids['strong'][:8]}"
    assert strong_ref in by_ref, "сильный кандидат должен попасть в подборку"
    assert selection["candidates"][0]["reference"] != f"cand-{ids['junior'][:8]}"


async def test_selection_explains_each_candidate(client: AsyncClient, db_factory) -> None:
    await _bank(client, db_factory)
    token = await _employer_token(client, "employer2@example.com")
    response = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Backend", "specialization_code": "backend", "grade": "middle", "stack": ["Python"]},
        headers=_auth(token),
    )
    card = response.json()["candidates"][0]
    codes = {r["code"] for r in card["reasons"]}
    assert "test_strength" in codes, "должно быть объяснение по результату теста"
    assert any("Подтверждённый профиль" in r["text"] for r in card["reasons"])
    assert card["score"] > 0


async def test_contacts_are_never_exposed_to_employer(client: AsyncClient, db_factory) -> None:
    await _bank(client, db_factory)
    token = await _employer_token(client, "employer3@example.com")
    response = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Backend", "specialization_code": "backend", "grade": "middle"},
        headers=_auth(token),
    )
    payload = json.dumps(response.json(), ensure_ascii=False)
    assert "@bank.ru" not in payload, "email кандидата не должен попадать в подборку"
    assert "+7 000" not in payload, "телефон кандидата не должен попадать в подборку"
    for card in response.json()["candidates"]:
        assert card["contacts_visible"] is False
        assert "contacts" not in card


async def test_other_employer_cannot_read_foreign_selection(client: AsyncClient, db_factory) -> None:
    await _bank(client, db_factory)
    owner = await _employer_token(client, "owner@example.com")
    stranger = await _employer_token(client, "stranger@example.com")
    created = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Backend", "specialization_code": "backend", "grade": "middle"},
        headers=_auth(owner),
    )
    selection_id = created.json()["id"]
    assert (
        await client.get(f"/api/v1/employers/me/selections/{selection_id}", headers=_auth(stranger))
    ).status_code == 404


async def test_refine_keeps_previous_selection(client: AsyncClient, db_factory) -> None:
    await _bank(client, db_factory)
    token = await _employer_token(client, "refiner@example.com")
    created = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Backend", "specialization_code": "backend", "grade": "middle", "stack": ["Python"]},
        headers=_auth(token),
    )
    first_id = created.json()["id"]
    first_count = len(created.json()["candidates"])

    refined = await client.post(
        f"/api/v1/employers/me/selections/{first_id}/refine",
        params={"stack": ["Python", "Docker", "Kafka"]},
        headers=_auth(token),
    )
    assert refined.status_code == 200, refined.text
    assert refined.json()["parent_selection_id"] == first_id
    assert refined.json()["id"] != first_id

    # Прежняя подборка не потеряна
    still = await client.get(f"/api/v1/employers/me/selections/{first_id}", headers=_auth(token))
    assert still.status_code == 200
    assert len(still.json()["candidates"]) == first_count

    listing = await client.get("/api/v1/employers/me/selections", headers=_auth(token))
    assert len(listing.json()) == 2


# --- Поиск по банку -----------------------------------------------------------


async def test_search_filters(client: AsyncClient, db_factory) -> None:
    await _bank(client, db_factory)
    token = await _employer_token(client, "searcher@example.com")

    all_candidates = await client.get("/api/v1/employers/me/search", headers=_auth(token))
    assert all_candidates.status_code == 200
    assert all_candidates.json()["total"] >= 5

    backend = await client.get(
        "/api/v1/employers/me/search", params={"specialization_code": "backend"}, headers=_auth(token)
    )
    assert all(c["specialization"] == "backend" for c in backend.json()["candidates"])

    juniors = await client.get(
        "/api/v1/employers/me/search", params={"grade": "junior"}, headers=_auth(token)
    )
    assert all(c["grade"] == "junior" for c in juniors.json()["candidates"])

    with_fsp = await client.get("/api/v1/employers/me/search", params={"has_fsp": True}, headers=_auth(token))
    assert all(c["fsp_achievements"] is not None for c in with_fsp.json()["candidates"])

    by_stack = await client.get(
        "/api/v1/employers/me/search", params={"stack": ["React"]}, headers=_auth(token)
    )
    assert by_stack.json()["total"] >= 2  # junior и frontend


async def test_privacy_hides_stack_and_experience(client: AsyncClient, db_factory) -> None:
    ids = await _bank(client, db_factory)
    token = await _employer_token(client, "privacy-view@example.com")
    response = await client.get(
        "/api/v1/employers/me/search",
        params={"specialization_code": "backend", "grade": "middle", "limit": 100},
        headers=_auth(token),
    )
    hidden_ref = f"cand-{ids['hidden'][:8]}"
    hidden = next(c for c in response.json()["candidates"] if c["reference"] == hidden_ref)
    assert hidden["stack"] == []
    assert hidden["experience_years"] is None
    assert hidden["fsp_achievements"] is None


async def test_search_requires_employer_role(client: AsyncClient, db_factory) -> None:
    await register_and_verify(client, "cand-search@example.com")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "cand-search@example.com", "password": "secret12345"}
    )
    token = login.json()["access_token"]
    assert (await client.get("/api/v1/employers/me/search", headers=_auth(token))).status_code == 403


async def test_need_validates_salary_range_and_grade(client: AsyncClient, db_factory) -> None:
    token = await _employer_token(client, "validator@example.com")
    bad_salary = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Тест", "salary_from": 300000, "salary_to": 100000},
        headers=_auth(token),
    )
    assert bad_salary.status_code == 400

    bad_grade = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Тест", "grade": "godlike"},
        headers=_auth(token),
    )
    assert bad_grade.status_code == 400

    bad_spec = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Тест", "specialization_code": "no-such"},
        headers=_auth(token),
    )
    assert bad_spec.status_code == 404
