"""Схемы аутентификации и согласий."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Минимум 8 символов")
    role: Literal["candidate", "employer"]
    consent_pdn: bool = Field(description="Согласие на обработку персональных данных (обязательно, 152-ФЗ)")
    consent_publish: bool = Field(
        default=False, description="Согласие на публикацию данных профиля работодателям"
    )


class RegisterResponse(BaseModel):
    user_id: str
    email: EmailStr
    role: str
    email_verified: bool
    message: str
    # В демо-режиме (mock-почта) токен отдаётся наружу, чтобы пройти подтверждение.
    # В продакшене отключено настройкой EXPOSE_DEV_TOKENS=false.
    verification_token: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Время жизни access-токена в секундах")


class ConsentUpdateRequest(BaseModel):
    publish: bool


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    role: str
    email_verified: bool
    is_active: bool
    fsp_id: str | None = None
    created_at: datetime
    consent_pdn_at: datetime | None = None
    consent_pdn_version: str | None = None
    consent_publish_at: datetime | None = None


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
