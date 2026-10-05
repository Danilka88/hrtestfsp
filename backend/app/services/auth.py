"""Бизнес-логика аутентификации.

Отделена от HTTP-слоя: функции принимают сессию БД и возвращают доменные объекты
или поднимают `AuthError`, который роутер преобразует в HTTP-ответ.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    utcnow,
    verify_password,
)
from app.models.user import EmailVerificationToken, RefreshToken, User, UserRole
from app.providers.registry import get_providers


class AuthError(Exception):
    """Ошибка аутентификации с HTTP-кодом и сообщением."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def _get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    role: str,
    consent_pdn: bool,
    consent_publish: bool,
) -> tuple[User, Optional[str]]:
    """Регистрация. Возвращает пользователя и (в демо-режиме) токен подтверждения."""
    settings = get_settings()

    if role not in UserRole.SELF_REGISTERABLE:
        raise AuthError(400, "Недопустимая роль для самостоятельной регистрации")
    if not consent_pdn:
        raise AuthError(400, "Требуется согласие на обработку персональных данных")

    normalized = normalize_email(email)
    if await _get_user_by_email(session, normalized):
        raise AuthError(409, "Пользователь с таким email уже зарегистрирован")

    now = utcnow()
    user = User(
        email=normalized,
        password_hash=hash_password(password),
        role=role,
        email_verified=False,
        is_active=True,
        consent_pdn_at=now,
        consent_pdn_version=settings.consent_version,
        consent_publish_at=now if consent_publish else None,
    )
    session.add(user)
    await session.flush()

    raw_token = new_opaque_token()
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=now + timedelta(minutes=settings.email_verification_ttl_minutes),
        )
    )
    await session.commit()
    await session.refresh(user)

    email_provider = get_providers().email
    await email_provider.send(
        user.email,
        "Подтверждение адреса электронной почты",
        f"Код подтверждения: {raw_token}",
    )

    return user, (raw_token if settings.expose_dev_tokens else None)


async def verify_email(session: AsyncSession, token: str) -> User:
    now = utcnow()
    result = await session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_opaque_token(token)
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise AuthError(400, "Недействительный токен подтверждения")
    if record.used_at is not None:
        raise AuthError(400, "Токен уже был использован")
    if record.expires_at < now:
        raise AuthError(400, "Срок действия токена истёк")

    record.used_at = now
    user = await session.get(User, record.user_id)
    if user is None:
        raise AuthError(404, "Пользователь не найден")

    user.email_verified = True
    await session.commit()
    await session.refresh(user)
    return user


def issue_tokens(session: AsyncSession, user: User) -> IssuedTokens:
    """Выдаёт пару access/refresh; refresh сохраняется по jti для возможности отзыва."""
    settings = get_settings()
    jti = str(uuid4())
    session.add(
        RefreshToken(
            jti=jti,
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return IssuedTokens(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, jti),
        expires_in=settings.access_token_ttl_minutes * 60,
    )


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    user = await _get_user_by_email(session, email)
    # Одинаковое сообщение для «нет пользователя» и «неверный пароль»,
    # чтобы не раскрывать существование аккаунта.
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError(401, "Неверный email или пароль")
    if not user.is_active:
        raise AuthError(403, "Учётная запись отключена")
    if not user.email_verified:
        raise AuthError(403, "Требуется подтверждение адреса электронной почты")
    return user


async def login(session: AsyncSession, *, email: str, password: str) -> tuple[User, IssuedTokens]:
    user = await authenticate(session, email=email, password=password)
    tokens = issue_tokens(session, user)
    await session.commit()
    return user, tokens


async def refresh(session: AsyncSession, *, refresh_token: str) -> IssuedTokens:
    """Ротация refresh-токена: старый отзывается, выдаётся новая пара."""
    from app.core.security import decode_token, REFRESH_TOKEN_TYPE

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != REFRESH_TOKEN_TYPE:
        raise AuthError(401, "Недействительный refresh-токен")

    jti = payload.get("jti")
    record = await session.get(RefreshToken, jti) if jti else None
    if record is None or record.revoked_at is not None or record.expires_at < utcnow():
        raise AuthError(401, "Refresh-токен отозван или истёк")

    user = await session.get(User, record.user_id)
    if user is None or not user.is_active:
        raise AuthError(401, "Пользователь недоступен")

    record.revoked_at = utcnow()
    tokens = issue_tokens(session, user)
    await session.commit()
    return tokens


async def logout(session: AsyncSession, *, refresh_token: str) -> None:
    from app.core.security import REFRESH_TOKEN_TYPE, decode_token

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != REFRESH_TOKEN_TYPE:
        return  # идемпотентно: недействительный токен просто нечего отзывать
    jti = payload.get("jti")
    record = await session.get(RefreshToken, jti) if jti else None
    if record is not None and record.revoked_at is None:
        record.revoked_at = utcnow()
        await session.commit()


async def update_publish_consent(session: AsyncSession, user: User, publish: bool) -> User:
    user.consent_publish_at = utcnow() if publish else None
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, user_id: str) -> Optional[User]:
    return await session.get(User, user_id)
