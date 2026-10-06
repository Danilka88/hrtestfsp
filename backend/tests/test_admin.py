"""Тесты кабинета администратора: доступ, метрики, схема взаимодействия, ИИ.

Проверяется и содержательная сторона: воронка считается по данным, ликвидность
не подменяется нулями, отсутствие данных честно выражается как `None`.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import User, UserRole
from tests.conftest import register_and_verify

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin12345"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _make_admin(client: AsyncClient, db_factory, email: str = ADMIN_EMAIL) -> str:
    """Администратор создаётся напрямую в БД: саморегистрация этой роли запрещена."""
    async with db_factory() as session:
        session.add(
            User(
                email=email,
                password_hash=hash_password(ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                email_verified=True,
                is_active=True,
            )
        )
        await session.commit()
    return await _login(client, email, ADMIN_PASSWORD)


# --- Доступ --------------------------------------------------------------------


async def test_admin_role_cannot_be_self_registered(client: AsyncClient) -> None:
    """Роль администратора не входит в список самостоятельно регистрируемых."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "fake-admin@example.com",
            "password": "secret12345",
            "role": "admin",
            "consent_pdn": True,
        },
    )
    assert response.status_code == 422


async def test_admin_endpoints_require_admin_role(client: AsyncClient, db_factory) -> None:
    await register_and_verify(client, "not-admin-cand@example.com", role="candidate")
    candidate_token = await _login(client, "not-admin-cand@example.com", "secret12345")
    await register_and_verify(client, "not-admin-emp@example.com", role="employer")
    employer_token = await _login(client, "not-admin-emp@example.com", "secret12345")

    for token in (candidate_token, employer_token):
        assert (await client.get("/api/v1/admin/overview", headers=_auth(token))).status_code == 403
        assert (await client.get("/api/v1/admin/interactions", headers=_auth(token))).status_code == 403
        assert (await client.post("/api/v1/admin/ai/summary", headers=_auth(token))).status_code == 403


async def test_admin_endpoints_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/overview")).status_code == 401


async def test_admin_can_read_ai_status(client: AsyncClient, db_factory) -> None:
    """Состояние модели читает и администратор: метка показывается в шапке кабинета."""
    admin_token = await _make_admin(client, db_factory)
    response = await client.get("/api/v1/ai/status", headers=_auth(admin_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert "available" in body and "degraded" in body and body["hint"]


# --- Метрики -------------------------------------------------------------------


async def test_overview_counts_both_sides_and_funnel(client: AsyncClient, db_factory) -> None:
    token = await _make_admin(client, db_factory)
    await register_and_verify(client, "for-admin-cand@example.com")
    await register_and_verify(client, "for-admin-emp@example.com", role="employer")

    response = await client.get("/api/v1/admin/overview", headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["people"]["candidates"] >= 1
    assert body["people"]["employers"] >= 1

    funnel = body["funnel"]
    assert [stage["key"] for stage in funnel] == [
        "registered",
        "profile",
        "tested",
        "categorized",
        "invited",
        "responded",
        "accepted",
    ]
    # Воронка не должна расти: каждый следующий шаг не больше предыдущего
    values = [stage["value"] for stage in funnel]
    assert values == sorted(values, reverse=True)

    for key in ("selection_rate", "contact_rate", "response_rate", "accept_rate"):
        assert key in body["liquidity"]
        assert "response_hours_median" in body["liquidity"]


async def test_empty_platform_reports_no_data_instead_of_zero(client: AsyncClient, db_factory) -> None:
    """На пустой базе доли — «нет данных» (None), а не «0%»: это разные утверждения."""
    token = await _make_admin(client, db_factory, "empty-admin@example.com")
    body = (await client.get("/api/v1/admin/overview", headers=_auth(token))).json()

    assert body["liquidity"]["response_rate"] is None
    assert body["liquidity"]["accept_rate"] is None
    assert body["liquidity"]["contact_rate"] is None
    assert body["liquidity"]["response_hours_median"] is None


async def test_categories_report_balance_and_empty_lists(client: AsyncClient, db_factory) -> None:
    token = await _make_admin(client, db_factory, "cat-admin@example.com")
    for path in (
        "/api/v1/admin/categories",
        "/api/v1/admin/companies",
        "/api/v1/admin/anomalies",
    ):
        response = await client.get(path, headers=_auth(token))
        assert response.status_code == 200, f"{path}: {response.text}"
        assert isinstance(response.json(), list)


async def test_interactions_schema_is_ready_for_drawing(client: AsyncClient, db_factory) -> None:
    token = await _make_admin(client, db_factory, "graph-admin@example.com")
    body = (await client.get("/api/v1/admin/interactions", headers=_auth(token))).json()

    assert set(body) >= {"employers", "candidates", "edges", "truncated"}
    assert isinstance(body["edges"], list)
    # Ограничение количества связей соблюдается, схема остаётся читаемой
    limited = (await client.get("/api/v1/admin/interactions?limit=5", headers=_auth(token))).json()
    assert len(limited["edges"]) <= 5


async def test_anomalies_flag_employer_without_contact(client: AsyncClient, db_factory) -> None:
    """Компания зарегистрирована, но приглашений не отправляла — сигнал для админа."""
    token = await _make_admin(client, db_factory, "anom-admin@example.com")
    await register_and_verify(client, "silent-emp@example.com", role="employer")

    anomalies = (await client.get("/api/v1/admin/anomalies", headers=_auth(token))).json()
    keys = {item["key"] for item in anomalies}
    assert "employers_without_invitations" in keys
    signal = next(item for item in anomalies if item["key"] == "employers_without_invitations")
    assert signal["severity"] == "info"
    assert signal["hint"]


# --- ИИ на дашборде ------------------------------------------------------------


async def test_admin_ai_summary_and_recommendations(client: AsyncClient, db_factory) -> None:
    """Без модели возвращаются подготовленные данные с пометкой degraded, а не ошибка."""
    token = await _make_admin(client, db_factory, "ai-admin@example.com")

    summary = await client.post("/api/v1/admin/ai/summary", headers=_auth(token))
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["data"]["headline"]
    assert body["data"]["summary"]
    assert body["provider"]
    assert isinstance(body["degraded"], bool)

    recommendations = await client.post("/api/v1/admin/ai/recommendations", headers=_auth(token))
    assert recommendations.status_code == 200, recommendations.text
    actions = recommendations.json()["data"]["actions"]
    assert actions and all(item.get("title") for item in actions)


async def test_admin_ai_uses_counted_metrics(client: AsyncClient, db_factory) -> None:
    """В сводку попадают реально посчитанные числа, а не заглушка.

    Проверяется на демо-ответе: он собирается из тех же метрик, поэтому число
    соискателей в тексте должно совпадать с числом из `/admin/overview`.
    """
    token = await _make_admin(client, db_factory, "metrics-admin@example.com")
    await register_and_verify(client, "counted-cand@example.com")

    overview = (await client.get("/api/v1/admin/overview", headers=_auth(token))).json()
    summary = (await client.post("/api/v1/admin/ai/summary", headers=_auth(token))).json()

    candidates = overview["people"]["candidates"]
    assert str(candidates) in summary["data"]["headline"]
