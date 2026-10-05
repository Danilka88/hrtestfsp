"""Протоколы внешних провайдеров.

Реальные и mock-реализации обязаны удовлетворять этим протоколам — это точка
подмены при переходе от демо к боевой интеграции.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class Provider(Protocol):
    name: str

    async def health(self) -> bool: ...


@runtime_checkable
class LLMProvider(Provider, Protocol):
    """Генерация/разбор текста: распознавание резюме, генерация заданий.

    Реализации: `OllamaLLMProvider` (реальная модель через Ollama) и
    `MockLLMProvider` (детерминированные демо-данные). Любая модель из
    библиотеки Ollama подходит без изменения кода — выбирается по имени.
    """

    async def extract_resume(self, text: str) -> dict: ...

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_schema: dict | None = None,
        max_tokens: int = 512,
    ) -> str: ...


@runtime_checkable
class EmbeddingProvider(Provider, Protocol):
    """Векторные представления текста для семантического сопоставления."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class ExternalIdentity:
    """Результат внешней аутентификации (локальной или через OIDC-провайдера)."""

    subject: str
    email: str
    claims: dict


@runtime_checkable
class AuthProvider(Provider, Protocol):
    """Аутентификация за абстракцией.

    Локальная реализация (`LocalAuthProvider`) проверяет пароль по хэшу и
    выпускает собственные JWT. При переходе на ФСП ID реализация заменяется на
    `KeycloakAuthProvider` (OIDC): бизнес-логика и API не меняются, потому что
    оба варианта приводятся к `ExternalIdentity`.
    """

    async def authenticate(self, email: str, password: str) -> ExternalIdentity | None: ...

    async def issue_tokens(self, identity: ExternalIdentity) -> dict[str, str]: ...


@dataclass(frozen=True)
class FspAchievement:
    """Достижение участника (схема определена командой — API ФСП не предоставлен)."""

    contest: str
    category: str
    year: int
    place: int | None = None
    rating: float | None = None


@runtime_checkable
class FspProvider(Provider, Protocol):
    """Реестр достижений ФСП. Обязательна корректная обработка отсутствия истории."""

    async def fetch_achievements(self, fsp_id: str) -> list[FspAchievement]: ...


@runtime_checkable
class EmailProvider(Provider, Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


@runtime_checkable
class StorageProvider(Provider, Protocol):
    async def save(self, key: str, data: bytes) -> str: ...
