"""Провайдеры аутентификации за общей абстракцией.

Зачем абстракция: в дальнейшем ФСП ID будет работать на Keycloak, поэтому способ
проверки учётных данных должен заменяться **без правок бизнес-логики**. Оба
провайдера приводят результат к `ExternalIdentity`, поэтому сервисный слой
(`app/services/auth.py`) и API не знают, какая реализация активна.

* `LocalAuthProvider` — активна в MVP: пароль проверяется по Argon2-хэшу,
  токены выпускаются собственные (JWT access + refresh с отзывом по `jti`).
* `KeycloakAuthProvider` — задел под ФСП ID: обмен учётных данных на токены в
  OIDC-эндпоинте realm и проверка подписи `id_token` по JWKS Keycloak.
  Включается настройкой `AUTH_PROVIDER=keycloak`; в демо не используется,
  потому что развёрнутого realm ФСП на хакатоне нет.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, utcnow, verify_password
from app.providers.base import ExternalIdentity

logger = logging.getLogger(__name__)


class AuthProviderUnavailable(RuntimeError):
    """Провайдер аутентификации недоступен или настроен не полностью."""


@dataclass(frozen=True)
class AuthCredentials:
    """Учётные данные, введённые пользователем."""

    email: str
    password: str


@dataclass(frozen=True)
class UserRecord:
    """Локальная запись пользователя (то, что даёт хранилище).

    Провайдеру передаётся уже загруженная запись: сам он в БД не ходит, поэтому
    его легко подменить и протестировать.
    """

    user_id: str
    email: str
    password_hash: str
    role: str


@dataclass(frozen=True)
class IssuedTokenPair:
    """Выпущенная пара токенов.

    `refresh_jti` заполняется только локальным провайдером: для собственных
    refresh-токенов нужна запись в БД, чтобы токен можно было отозвать.
    Внешний провайдер управляет жизненным циклом токенов сам.
    """

    access_token: str
    refresh_token: str
    expires_in: int
    refresh_jti: str | None = None
    refresh_expires_at: datetime | None = None


class LocalAuthProvider:
    """Собственная аутентификация: Argon2 + JWT. Активна по умолчанию."""

    name = "auth:local"

    async def health(self) -> bool:
        return True

    async def authenticate(
        self,
        credentials: AuthCredentials,
        record: UserRecord | None,
    ) -> ExternalIdentity | None:
        if record is None:
            return None
        if not verify_password(credentials.password, record.password_hash):
            return None
        return ExternalIdentity(
            subject=record.user_id,
            email=record.email,
            claims={"role": record.role, "auth_provider": "local"},
        )

    async def issue_tokens(self, identity: ExternalIdentity, *, role: str) -> IssuedTokenPair:
        settings = get_settings()
        jti = str(uuid4())
        return IssuedTokenPair(
            access_token=create_access_token(identity.subject, role),
            refresh_token=create_refresh_token(identity.subject, jti),
            expires_in=settings.access_token_ttl_minutes * 60,
            refresh_jti=jti,
            refresh_expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
        )


class KeycloakAuthProvider:
    """Задел под ФСП ID на Keycloak (OIDC Resource Owner Password Grant).

    Реализована целиком, но в MVP не активна: нужен развёрнутый realm ФСП.
    Включается настройками `AUTH_PROVIDER=keycloak` и `KEYCLOAK_*`.
    """

    name = "auth:keycloak"

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = (settings.keycloak_base_url or "").rstrip("/")
        self.realm = settings.keycloak_realm
        self.client_id = settings.keycloak_client_id
        self.client_secret = settings.keycloak_client_secret
        self.timeout = settings.http_timeout_seconds

    def _token_endpoint(self) -> str:
        return f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token"

    def _jwks_endpoint(self) -> str:
        return f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/certs"

    def _require_config(self) -> None:
        if not (self.base_url and self.realm and self.client_id):
            raise AuthProviderUnavailable(
                "Keycloak не настроен: задайте KEYCLOAK_BASE_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID"
            )

    async def health(self) -> bool:
        try:
            self._require_config()
        except AuthProviderUnavailable:
            return False
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/realms/{self.realm}/.well-known/openid-configuration"
                )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def authenticate(
        self,
        credentials: AuthCredentials,
        record: UserRecord | None,  # не используется: учётные данные проверяет Keycloak
    ) -> ExternalIdentity | None:
        """Обмен учётных данных на токены realm и разбор подписанного id_token."""
        self._require_config()
        payload = {
            "grant_type": "password",
            "client_id": self.client_id,
            "username": credentials.email,
            "password": credentials.password,
            "scope": "openid email profile",
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self._token_endpoint(), data=payload)
        except httpx.HTTPError as exc:
            raise AuthProviderUnavailable(f"Keycloak недоступен: {exc}") from exc

        if response.status_code == 401:
            return None  # неверные учётные данные — как и у локального провайдера
        if response.status_code >= 400:
            raise AuthProviderUnavailable(f"Keycloak вернул {response.status_code}")

        claims = self._verify_id_token(response.json().get("id_token"))
        subject = claims.get("sub")
        email = claims.get("email") or credentials.email
        if not subject:
            raise AuthProviderUnavailable("В id_token отсутствует идентификатор пользователя")
        # Токены realm передаём дальше в claims: их выдаёт Keycloak, локально
        # ничего выпускать и хранить не нужно.
        claims = {
            **claims,
            "_access_token": response.json().get("access_token"),
            "_refresh_token": response.json().get("refresh_token"),
            "expires_in": response.json().get("expires_in"),
            "auth_provider": "keycloak",
        }
        return ExternalIdentity(subject=str(subject), email=str(email), claims=claims)

    def _verify_id_token(self, id_token: str | None) -> dict[str, Any]:
        """Проверяет подпись id_token по JWKS realm — без этого доверять claims нельзя."""
        if not id_token:
            raise AuthProviderUnavailable("Keycloak не вернул id_token")
        import jwt  # локальный импорт: PyJWT нужен только в этом режиме

        try:
            signing_key = jwt.PyJWKClient(self._jwks_endpoint()).get_signing_key_from_jwt(id_token)
            return jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                options={"verify_aud": bool(self.client_id)},
            )
        except Exception as exc:  # noqa: BLE001 — любая ошибка проверки = отказ
            raise AuthProviderUnavailable(f"id_token не прошёл проверку: {exc}") from exc

    async def issue_tokens(self, identity: ExternalIdentity, *, role: str) -> IssuedTokenPair:
        """Токены выпускает сам Keycloak; локальная запись refresh не создаётся."""
        access = identity.claims.get("_access_token")
        refresh = identity.claims.get("_refresh_token")
        if not access or not refresh:
            raise AuthProviderUnavailable("Keycloak не вернул пару токенов")
        return IssuedTokenPair(
            access_token=str(access),
            refresh_token=str(refresh),
            expires_in=int(identity.claims.get("expires_in") or 300),
            refresh_jti=None,
        )


def get_auth_provider() -> LocalAuthProvider | KeycloakAuthProvider:
    """Активный провайдер аутентификации по настройке AUTH_PROVIDER."""
    mode = (get_settings().auth_provider or "local").lower()
    if mode == "keycloak":
        return KeycloakAuthProvider()
    return LocalAuthProvider()
