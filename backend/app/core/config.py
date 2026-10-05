"""Конфигурация приложения.

Все параметры читаются из переменных окружения / .env.
Внешние провайдеры по умолчанию — mock (демо воспроизводимо оффлайн).
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
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
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30

    # --- Провайдеры: mock | real ---
    llm_provider: str = "mock"
    fsp_provider: str = "mock"
    email_provider: str = "mock"
    storage_provider: str = "mock"

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Настройки читаются один раз и кэшируются."""
    return Settings()
