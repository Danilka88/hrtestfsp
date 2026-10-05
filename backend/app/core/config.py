"""Конфигурация приложения.

Все параметры читаются из переменных окружения / .env.
Внешние провайдеры по умолчанию — mock (демо воспроизводимо оффлайн).
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Приложение ---
    app_name: str = "IT-Talent Match API"
    app_version: str = "0.1.0"
    environment: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- Слой хранения ---
    database_url: str = "postgresql+asyncpg://app:app@db:5432/app"
    redis_url: str = "redis://redis:6379/0"

    # --- Безопасность ---
    jwt_secret: str = "dev-insecure-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30

    # --- Провайдеры: mock | real ---
    llm_provider: str = "mock"
    fsp_provider: str = "mock"
    email_provider: str = "mock"
    storage_provider: str = "mock"

    # --- Аутентификация ---
    email_verification_ttl_minutes: int = 24 * 60
    consent_version: str = "pdn-v1"
    # В демо-режиме (mock-почта) токен подтверждения отдаётся в ответе API.
    # В продакшене обязательно False.
    expose_dev_tokens: bool = True

    # --- Правила продукта ---
    grade_change_cooldown_days: int = 90

    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8080",
        ]
    )


    @model_validator(mode="after")
    def _validate_security_settings(self) -> "Settings":
        """Защита от запуска с небезопасным секретом вне локального окружения."""
        if self.environment != "local":
            if len(self.jwt_secret) < 32 or "change-me" in self.jwt_secret or "insecure" in self.jwt_secret:
                raise ValueError(
                    "JWT_SECRET должен быть не короче 32 символов и не содержать "
                    "заглушек ('change-me', 'insecure') вне локального окружения"
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Настройки читаются один раз и кэшируются."""
    return Settings()
