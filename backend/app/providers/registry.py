"""Реестр провайдеров: выбор реализации по конфигурации.

Возвращается типизированный объект, а не словарь, — обращения вида
`get_providers().email` проверяются статически.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.providers import mock
from app.providers.base import EmailProvider, FspProvider, LLMProvider, Provider, StorageProvider


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

    На текущем этапе реальные реализации отсутствуют: настройки `*_provider = real`
    пока разрешаются в mock-реализации (точка расширения для Этапа 5+).
    """
    _settings = get_settings()  # читается для будущего выбора реализации
    return Providers(
        llm=mock.MockLLMProvider(),
        fsp=mock.MockFspProvider(),
        email=mock.MockEmailProvider(),
        storage=mock.MockStorageProvider(),
    )


def get_llm() -> LLMProvider:
    return get_providers().llm


def get_fsp() -> FspProvider:
    return get_providers().fsp


def get_email() -> EmailProvider:
    return get_providers().email
