"""Тесты защитных проверок конфигурации."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_local_allows_placeholder_secret() -> None:
    settings = Settings(environment="local", jwt_secret="change-me")
    assert settings.jwt_secret == "change-me"


def test_short_secret_rejected_outside_local() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret="short-secret")


def test_placeholder_secret_rejected_outside_local() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret="change-me-please-change-me-now-32")


def test_strong_secret_allowed_outside_local() -> None:
    settings = Settings(environment="production", jwt_secret="Z" * 48)
    assert settings.environment == "production"
    assert settings.expose_dev_tokens is True  # значение по умолчанию; в проде задаётся false


def test_dev_token_exposure_can_be_disabled() -> None:
    settings = Settings(expose_dev_tokens=False)
    assert settings.expose_dev_tokens is False
