"""Тесты абстракции аутентификации.

Проверяется, что способ проверки учётных данных действительно вынесен за
интерфейс: локальная реализация работает, а реализация Keycloak для будущего
ФСП ID корректно сообщает о неготовности вместо тихой ошибки.
"""

from __future__ import annotations

import pytest

from app.core.security import hash_password
from app.providers.auth import (
    AuthCredentials,
    AuthProviderUnavailable,
    KeycloakAuthProvider,
    LocalAuthProvider,
    UserRecord,
    get_auth_provider,
)

PASSWORD = "secret12345"


def _record() -> UserRecord:
    return UserRecord(
        user_id="user-1",
        email="candidate@example.com",
        password_hash=hash_password(PASSWORD),
        role="candidate",
    )


async def test_local_provider_authenticates_correct_password():
    provider = LocalAuthProvider()
    identity = await provider.authenticate(
        AuthCredentials(email="candidate@example.com", password=PASSWORD), _record()
    )
    assert identity is not None
    assert identity.subject == "user-1"
    assert identity.email == "candidate@example.com"


async def test_local_provider_rejects_wrong_password():
    provider = LocalAuthProvider()
    assert (
        await provider.authenticate(
            AuthCredentials(email="candidate@example.com", password="неверный"), _record()
        )
        is None
    )


async def test_local_provider_rejects_missing_record():
    """Несуществующий пользователь не должен отличаться от неверного пароля по ответу."""
    provider = LocalAuthProvider()
    assert (
        await provider.authenticate(AuthCredentials(email="nobody@example.com", password=PASSWORD), None)
        is None
    )


async def test_local_provider_issues_revocable_pair():
    provider = LocalAuthProvider()
    identity = await provider.authenticate(
        AuthCredentials(email="candidate@example.com", password=PASSWORD), _record()
    )
    assert identity is not None
    pair = await provider.issue_tokens(identity, role="candidate")
    assert pair.access_token and pair.refresh_token
    assert pair.expires_in > 0
    # Локальному провайдеру нужен jti, чтобы refresh можно было отозвать
    assert pair.refresh_jti is not None
    assert pair.refresh_expires_at is not None


def test_default_provider_is_local():
    assert isinstance(get_auth_provider(), LocalAuthProvider)


async def test_keycloak_provider_requires_configuration():
    """Без параметров realm реализация обязана явно сообщать о неготовности."""
    provider = KeycloakAuthProvider()
    assert await provider.health() is False
    with pytest.raises(AuthProviderUnavailable):
        await provider.authenticate(AuthCredentials(email="user@example.com", password="whatever"), None)


async def test_keycloak_issue_tokens_requires_tokens_from_realm():
    from app.providers.base import ExternalIdentity

    provider = KeycloakAuthProvider()
    identity = ExternalIdentity(subject="1", email="user@example.com", claims={})
    with pytest.raises(AuthProviderUnavailable):
        await provider.issue_tokens(identity, role="candidate")


async def test_login_flow_uses_provider(client):
    """Сквозная проверка: вход через API проходит через активный провайдер."""
    from tests.conftest import register_and_verify

    await register_and_verify(client, "provider.flow@example.com", password=PASSWORD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "provider.flow@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]

    wrong = await client.post(
        "/api/v1/auth/login",
        json={"email": "provider.flow@example.com", "password": "неверный"},
    )
    assert wrong.status_code == 401
    assert "Неверный email или пароль" in wrong.json()["detail"]
