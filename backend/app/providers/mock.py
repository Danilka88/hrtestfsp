"""Mock-реализации провайдеров (режим по умолчанию).

Позволяют демонстрировать сквозной сценарий без интернета и платных сервисов.
"""

from __future__ import annotations

import logging
import re
from typing import List

from app.providers.base import FspAchievement

logger = logging.getLogger(__name__)


class MockLLMProvider:
    name = "llm:mock"

    async def health(self) -> bool:
        return True

    async def extract_resume(self, text: str) -> dict:
        """Простейший детерминированный разбор без внешних вызовов.

        На Этапе 2 заменяется/дополняется реальным провайдером за тем же интерфейсом.
        """
        email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text or "")
        phone = re.search(r"\+?\d[\d\s\-()]{9,}\d", text or "")
        return {
            "full_name": None,
            "contacts": {
                "email": email.group(0) if email else None,
                "phone": phone.group(0) if phone else None,
            },
            "stack": [],
            "grade": None,
            "roles": [],
            "experience_years": None,
            "soft_skills": [],
            "source": "mock",
        }


class MockFspProvider:
    name = "fsp:mock"

    async def health(self) -> bool:
        return True

    async def fetch_achievements(self, fsp_id: str) -> List[FspAchievement]:
        """Синтетические достижения.

        Пустой/неизвестный идентификатор возвращает пустой список — ветка
        «нет истории ФСП» должна обрабатываться корректно.
        """
        if not fsp_id:
            return []
        if fsp_id.endswith("0"):
            return []
        return [
            FspAchievement(
                contest="Региональный чемпионат по программированию",
                category="алгоритмическое программирование",
                year=2025,
                place=2,
                rating=1480.0,
            )
        ]


class MockEmailProvider:
    name = "email:mock"

    async def health(self) -> bool:
        return True

    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info("[mock-email] to=%s subject=%s", to, subject)


class MockStorageProvider:
    name = "storage:mock"

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def health(self) -> bool:
        return True

    async def save(self, key: str, data: bytes) -> str:
        self._store[key] = data
        return f"mock://{key}"
