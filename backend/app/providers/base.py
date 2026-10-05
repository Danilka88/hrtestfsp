"""Протоколы внешних провайдеров.

Реальные и mock-реализации обязаны удовлетворять этим протоколам — это точка
подмены при переходе от демо к боевой интеграции.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, runtime_checkable


class Provider(Protocol):
    name: str

    async def health(self) -> bool: ...


@runtime_checkable
class LLMProvider(Provider, Protocol):
    """Генерация/разбор текста: распознавание резюме, генерация заданий."""

    async def extract_resume(self, text: str) -> dict: ...


@dataclass(frozen=True)
class FspAchievement:
    """Достижение участника (схема определена командой — API ФСП не предоставлен)."""

    contest: str
    category: str
    year: int
    place: Optional[int] = None
    rating: Optional[float] = None


@runtime_checkable
class FspProvider(Provider, Protocol):
    """Реестр достижений ФСП. Обязательна корректная обработка отсутствия истории."""

    async def fetch_achievements(self, fsp_id: str) -> List[FspAchievement]: ...


@runtime_checkable
class EmailProvider(Provider, Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


@runtime_checkable
class StorageProvider(Provider, Protocol):
    async def save(self, key: str, data: bytes) -> str: ...
