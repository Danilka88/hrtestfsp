"""Тесты абстракции аутентификации.

Проверяется, что способ проверки учётных данных действительно вынесен за
интерфейс: локальная реализация работает, а реализация Keycloak для будущего
ФСП ID корректно сообщает о неготовности вместо тихой ошибки.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import get_settings
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


# --- служебные свойства локального провайдера --------------------------------


async def test_local_provider_is_always_healthy():
    assert await LocalAuthProvider().health() is True
    assert LocalAuthProvider.name == "auth:local"


async def test_local_identity_carries_role_claim():
    """Сервисный слой получает роль из identity, а не из хранилища напрямую."""
    identity = await LocalAuthProvider().authenticate(
        AuthCredentials(email="candidate@example.com", password=PASSWORD), _record()
    )
    assert identity is not None
    assert identity.claims["role"] == "candidate"
    assert identity.claims["auth_provider"] == "local"


# --- реализация Keycloak (задел под ФСП ID) ----------------------------------


def _keycloak(monkeypatch, handler) -> KeycloakAuthProvider:
    """Провайдер Keycloak с настроенным realm и подменённым HTTP."""
    monkeypatch.setenv("KEYCLOAK_BASE_URL", "http://kc.test")
    monkeypatch.setenv("KEYCLOAK_REALM", "fsp")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "it-talent")
    monkeypatch.setenv("KEYCLOAK_CLIENT_SECRET", "s3cret")
    get_settings.cache_clear()

    # Настоящий класс запоминаем до подмены: `app.providers.auth.httpx` — тот же
    # модуль, что и здесь, поэтому обращение к httpx.AsyncClient внутри фабрики
    # иначе попало бы в неё же.
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(handler), base_url="http://kc.test")

    monkeypatch.setattr("app.providers.auth.httpx.AsyncClient", factory)
    return KeycloakAuthProvider()


class _KeycloakHandler:
    """Подменяет точки Keycloak: well-known, token и JWKS."""

    def __init__(self, *, status: int = 200, body: dict | None = None, error: Exception | None = None):
        self.status = status
        self.body = body if body is not None else {}
        self.error = error
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        if self.error is not None:
            raise self.error
        return httpx.Response(self.status, json=self.body)


def test_keycloak_endpoints_are_built_from_realm(monkeypatch):
    provider = _keycloak(monkeypatch, _KeycloakHandler())
    assert provider._token_endpoint() == "http://kc.test/realms/fsp/protocol/openid-connect/token"
    assert provider._jwks_endpoint() == "http://kc.test/realms/fsp/protocol/openid-connect/certs"
    get_settings.cache_clear()


async def test_keycloak_health_true_when_realm_responds(monkeypatch):
    handler = _KeycloakHandler(status=200, body={"issuer": "http://kc.test/realms/fsp"})
    provider = _keycloak(monkeypatch, handler)
    assert await provider.health() is True
    assert any("well-known/openid-configuration" in url for url in handler.requests)
    get_settings.cache_clear()


async def test_keycloak_health_false_on_network_error(monkeypatch):
    provider = _keycloak(monkeypatch, _KeycloakHandler(error=httpx.ConnectError("нет сети")))
    assert await provider.health() is False
    get_settings.cache_clear()


async def test_keycloak_sends_password_grant_with_client_secret(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(httpx.QueryParams(request.content.decode())))
        return httpx.Response(401, json={"error": "invalid_grant"})

    provider = _keycloak(monkeypatch, handler)
    result = await provider.authenticate(AuthCredentials(email="user@example.com", password="pw"), None)
    # Неверные учётные данные у Keycloak выглядят так же, как у локального провайдера
    assert result is None
    assert seen["grant_type"] == "password"
    assert seen["client_secret"] == "s3cret"
    assert seen["username"] == "user@example.com"
    get_settings.cache_clear()


async def test_keycloak_server_error_is_not_a_credential_failure(monkeypatch):
    """Ошибка realm (5xx) не должна выглядеть как «неверный пароль»."""
    provider = _keycloak(monkeypatch, _KeycloakHandler(status=503))
    with pytest.raises(AuthProviderUnavailable) as error:
        await provider.authenticate(AuthCredentials(email="u@example.com", password="pw"), None)
    assert "503" in str(error.value)
    get_settings.cache_clear()


async def test_keycloak_requires_id_token_in_response(monkeypatch):
    provider = _keycloak(monkeypatch, _KeycloakHandler(status=200, body={"access_token": "a"}))
    with pytest.raises(AuthProviderUnavailable) as error:
        await provider.authenticate(AuthCredentials(email="u@example.com", password="pw"), None)
    assert "id_token" in str(error.value)
    get_settings.cache_clear()


async def test_keycloak_rejects_unverifiable_id_token(monkeypatch):
    """Подпись id_token обязательна: без проверки доверять claims нельзя."""
    provider = _keycloak(monkeypatch, _KeycloakHandler(status=200, body={"id_token": "подделка"}))
    with pytest.raises(AuthProviderUnavailable) as error:
        await provider.authenticate(AuthCredentials(email="u@example.com", password="pw"), None)
    assert "не прошёл проверку" in str(error.value)
    get_settings.cache_clear()


async def test_keycloak_maps_verified_claims_to_identity(monkeypatch):
    """Проверенный id_token превращается в identity, а токены realm — в claims."""
    import jwt as pyjwt

    provider = _keycloak(
        monkeypatch,
        _KeycloakHandler(
            status=200,
            body={
                "id_token": "подписанный",
                "access_token": "realm-access",
                "refresh_token": "realm-refresh",
                "expires_in": 300,
            },
        ),
    )
    monkeypatch.setattr(
        pyjwt,
        "PyJWKClient",
        lambda url: type(
            "_C", (), {"get_signing_key_from_jwt": lambda self, token: type("_K", (), {"key": "k"})()}
        )(),
    )
    monkeypatch.setattr(pyjwt, "decode", lambda *a, **k: {"sub": "kc-1", "email": "user@example.com"})

    identity = await provider.authenticate(AuthCredentials(email="u@example.com", password="pw"), None)
    assert identity is not None
    assert identity.subject == "kc-1"
    assert identity.email == "user@example.com"
    assert identity.claims["auth_provider"] == "keycloak"

    pair = await provider.issue_tokens(identity, role="candidate")
    assert pair.access_token == "realm-access"
    assert pair.refresh_token == "realm-refresh"
    # Токены выпускает Keycloak — локальная запись refresh не создаётся
    assert pair.refresh_jti is None
    assert pair.expires_in == 300
    get_settings.cache_clear()


async def test_keycloak_identity_without_subject_is_rejected(monkeypatch):
    import jwt as pyjwt

    provider = _keycloak(
        monkeypatch, _KeycloakHandler(status=200, body={"id_token": "t", "access_token": "a"})
    )
    monkeypatch.setattr(
        pyjwt,
        "PyJWKClient",
        lambda url: type(
            "_C", (), {"get_signing_key_from_jwt": lambda self, token: type("_K", (), {"key": "k"})()}
        )(),
    )
    monkeypatch.setattr(pyjwt, "decode", lambda *a, **k: {"email": "no-sub@example.com"})

    with pytest.raises(AuthProviderUnavailable) as error:
        await provider.authenticate(AuthCredentials(email="u@example.com", password="pw"), None)
    assert "идентификатор" in str(error.value)
    get_settings.cache_clear()


def test_provider_is_selected_by_setting(monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "keycloak")
    get_settings.cache_clear()
    assert isinstance(get_auth_provider(), KeycloakAuthProvider)

    monkeypatch.setenv("AUTH_PROVIDER", "local")
    get_settings.cache_clear()
    assert isinstance(get_auth_provider(), LocalAuthProvider)
    get_settings.cache_clear()
