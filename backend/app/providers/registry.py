"""Реестр провайдеров: выбор реализации по конфигурации."""

from __future__ import annotations

from typing import Dict, Protocol

from app.core.config import get_settings
from app.providers import mock


class _Named(Protocol):
    name: str

    async def health(self) -> bool: ...


def get_providers() -> Dict[str, _Named]:
    """Возвращает активные провайдеры.

    На Этапе 0 реальные реализации отсутствуют — конфигурация `*_provider = real`
    пока приводит к mock-реализации с предупреждением (точка расширения).
    """
    settings = get_settings()
    return {
        "llm": mock.MockLLMProvider(),
        "fsp": mock.MockFspProvider(),
        "email": mock.MockEmailProvider(),
        "storage": mock.MockStorageProvider(),
    }


def get_llm() -> mock.MockLLMProvider:
    return get_providers()["llm"]  # type: ignore[return-value]


def get_fsp() -> mock.MockFspProvider:
    return get_providers()["fsp"]  # type: ignore[return-value]
