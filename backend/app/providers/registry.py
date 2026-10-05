"""Реестр провайдеров: выбор реализации по конфигурации.

Возвращается типизированный объект, а не словарь, — обращения вида
`get_providers().email` проверяются статически.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.providers import mock
from app.providers.base import EmailProvider, FspProvider, LLMProvider, Provider, StorageProvider
from app.providers.resilient import ResilientLLMProvider, build_llm_provider

# Провайдер LLM создаётся один раз: он кэширует имя выбранной модели и
# последнее наблюдение о доступности, которые показываются в интерфейсе.
_llm: ResilientLLMProvider | None = None


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    fsp: FspProvider
    email: EmailProvider
    storage: StorageProvider

    def as_dict(self) -> dict[str, Provider]:
        return {
            "llm": self.llm,
            "fsp": self.fsp,
            "email": self.email,
            "storage": self.storage,
        }


def get_providers() -> Providers:
    """Активные провайдеры.

    LLM: реальная локальная модель (Ollama) с автоматическим откатом на
    демо-данные — управляется настройкой `LLM_PROVIDER`. Остальные внешние
    сервисы пока работают в mock-режиме: демо воспроизводимо оффлайн.
    """
    return Providers(
        llm=get_llm(),
        fsp=mock.MockFspProvider(),
        email=mock.MockEmailProvider(),
        storage=mock.MockStorageProvider(),
    )


def get_llm() -> ResilientLLMProvider:
    global _llm
    if _llm is None:
        _llm = build_llm_provider()
    return _llm


def reset_llm_provider() -> None:
    """Сброс кэша провайдера LLM (используется в тестах и при смене настроек)."""
    global _llm
    _llm = None


def get_fsp() -> FspProvider:
    return get_providers().fsp


def get_email() -> EmailProvider:
    return get_providers().email
