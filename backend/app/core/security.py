"""Безопасность: хеширование паролей, JWT, работа с токенами.

Все временные метки — наивный UTC (без tzinfo) для переносимости между
PostgreSQL и SQLite, который используется в тестах.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

_hasher = PasswordHasher()


# --- Время ---------------------------------------------------------------

def utcnow() -> datetime:
    """Текущее время UTC (naive)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Пароли --------------------------------------------------------------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверка пароля. Любая ошибка хеша трактуется как неверный пароль."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# --- Одноразовые токены (подтверждение email) ----------------------------

def new_opaque_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def hash_opaque_token(token: str) -> str:
    """В БД хранится только хеш токена — утечка таблицы не даёт его использовать."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- JWT -----------------------------------------------------------------

def _encode(payload: Dict[str, Any], expires_delta: timedelta, secret: str, algorithm: str) -> str:
    now = utcnow()
    to_encode = dict(payload)
    to_encode.update({"iat": now, "exp": now + expires_delta})
    return jwt.encode(to_encode, secret, algorithm=algorithm)


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    return _encode(
        {"sub": user_id, "role": role, "type": ACCESS_TOKEN_TYPE},
        timedelta(minutes=settings.access_token_ttl_minutes),
        settings.jwt_secret,
        settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str, jti: str) -> str:
    settings = get_settings()
    return _encode(
        {"sub": user_id, "jti": jti, "type": REFRESH_TOKEN_TYPE},
        timedelta(days=settings.refresh_token_ttl_days),
        settings.jwt_secret,
        settings.jwt_algorithm,
    )


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Декодирует и валидирует токен. Возвращает None при любой ошибке."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def refresh_token_ttl_days() -> int:
    return get_settings().refresh_token_ttl_days
