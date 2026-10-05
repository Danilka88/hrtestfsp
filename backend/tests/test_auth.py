"""Тесты аутентификации, ролей и согласий (152-ФЗ)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import register_and_verify


async def test_register_requires_pdn_consent(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "no-consent@example.com", "password": "secret12345",
              "role": "candidate", "consent_pdn": False},
    )
    assert response.status_code == 400
    assert "согласие" in response.json()["detail"].lower()


async def test_register_rejects_admin_role(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "password": "secret12345",
              "role": "admin", "consent_pdn": True},
    )
    assert response.status_code == 422  # роль не входит в допустимый литерал схемы


async def test_register_creates_unverified_user_and_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "New.User@Example.com", "password": "secret12345",
              "role": "candidate", "consent_pdn": True},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"       # email нормализуется
    assert body["email_verified"] is False
    assert body["verification_token"]                    # демо-режим отдаёт токен
    assert body["role"] == "candidate"


async def test_duplicate_email_rejected(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "secret12345",
               "role": "candidate", "consent_pdn": True}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_short_password_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "1234",
              "role": "candidate", "consent_pdn": True},
    )
    assert response.status_code == 422


async def test_login_requires_verified_email(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "unverified@example.com", "password": "secret12345",
              "role": "candidate", "consent_pdn": True},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": "unverified@example.com", "password": "secret12345"}
    )
    assert response.status_code == 403
    assert "подтвержд" in response.json()["detail"].lower()


async def test_verify_email_with_invalid_token(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
    assert response.status_code == 400


async def test_full_flow_register_verify_login_me(client: AsyncClient) -> None:
    profile = await register_and_verify(client, "flow@example.com")
    assert profile["email_verified"] is True
    assert profile["consent_pdn_at"] is not None

    login = await client.post(
        "/api/v1/auth/login", json={"email": "flow@example.com", "password": "secret12345"}
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["expires_in"] > 0

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "flow@example.com"


async def test_wrong_password_is_indistinguishable_from_unknown_user(client: AsyncClient) -> None:
    await register_and_verify(client, "known@example.com")
    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "known@example.com", "password": "wrong-password"}
    )
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "wrong-password"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


async def test_me_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    bad = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer broken"})
    assert bad.status_code == 401


async def test_refresh_rotates_and_invalidates_old_token(client: AsyncClient) -> None:
    await register_and_verify(client, "rotate@example.com")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "rotate@example.com", "password": "secret12345"}
    )
    old_refresh = login.json()["refresh_token"]

    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]
    assert new_refresh != old_refresh

    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401  # старый токен отозван

    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})).status_code == 200


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    await register_and_verify(client, "logout@example.com")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "logout@example.com", "password": "secret12345"}
    )
    refresh_token = login.json()["refresh_token"]

    assert (await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})).status_code == 200
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})).status_code == 401


async def test_publish_consent_can_be_toggled(client: AsyncClient) -> None:
    await register_and_verify(client, "consent@example.com")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "consent@example.com", "password": "secret12345"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    on = await client.patch("/api/v1/auth/consents", json={"publish": True}, headers=headers)
    assert on.status_code == 200 and on.json()["consent_publish_at"] is not None

    off = await client.patch("/api/v1/auth/consents", json={"publish": False}, headers=headers)
    assert off.status_code == 200 and off.json()["consent_publish_at"] is None


async def test_role_separation_between_candidate_and_employer(client: AsyncClient) -> None:
    candidate = await register_and_verify(client, "worker@example.com", role="candidate")
    employer = await register_and_verify(client, "company@example.com", role="employer")
    assert candidate["role"] == "candidate"
    assert employer["role"] == "employer"
