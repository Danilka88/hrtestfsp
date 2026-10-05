"""Mock-реализации провайдеров (режим по умолчанию).

Позволяют демонстрировать сквозной сценарий без интернета и платных сервисов.
Разбор резюме детерминированный, по словарю технологий: этого достаточно для
демо и тестов, а реальный LLM подключается за тем же интерфейсом.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

from app.providers.base import FspAchievement

logger = logging.getLogger(__name__)

# Словарь технологий. Поиск идёт по подстроке в тексте, приведённом к нижнему регистру.
_STACK_ALIASES: Dict[str, List[str]] = {
    "Python": ["python", "питон"],
    "Java": ["java"],
    "Go": ["golang"],
    "JavaScript": ["javascript"],
    "TypeScript": ["typescript"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "PHP": ["php"],
    "Ruby": ["ruby"],
    "Scala": ["scala"],
    "Rust": ["rust"],
    "PostgreSQL": ["postgresql", "postgres", "посгрес"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "ClickHouse": ["clickhouse"],
    "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Git": ["git"],
    "Linux": ["linux"],
    "React": ["react"],
    "Vue": ["vue"],
    "Angular": ["angular"],
    "Django": ["django"],
    "FastAPI": ["fastapi"],
    "Spring": ["spring"],
    "Node.js": ["node.js", "nodejs"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Airflow": ["airflow"],
    "Spark": ["spark"],
}

_ROLE_HINTS: Dict[str, List[str]] = {
    "backend": ["backend", "бэкенд", "back-end"],
    "frontend": ["frontend", "фронтенд", "front-end"],
    "fullstack": ["fullstack", "full-stack", "фулстек"],
    "devops": ["devops", "sre"],
    "qa": ["qa ", "тестировщик", "тестирование"],
    "analyst": ["аналитик", "analyst"],
    "data": ["data engineer", "дата-инженер", "ml engineer"],
    "mobile": ["android", "ios ", "мобильн"],
}

# Порядок важен: проверяем от старшего грейда к младшему.
_GRADE_HINTS = [
    ("lead", ["lead", "тимлид", "team lead", "руководитель разработки"]),
    ("senior", ["senior", "сеньор", "старший"]),
    ("middle", ["middle", "мидл", "средний"]),
    ("junior", ["junior", "джун", "младший", "стажёр", "стажер", "intern"]),
]

_SOFT_HINTS = ["команд", "коммуника", "ответствен", "ментор", "наставни",
               "лидер", "самостоятельн", "инициатив"]


class MockLLMProvider:
    name = "llm:mock"

    async def health(self) -> bool:
        return True

    async def extract_resume(self, text: str) -> dict:
        """Детерминированный разбор резюме без внешних вызовов.

        Возвращаются только реально найденные в тексте значения: отсутствующие
        поля остаются пустыми и не додумываются.
        """
        source = text or ""
        lowered = source.lower()

        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", source)
        phone_match = re.search(r"\+?\d[\d\s\-()]{9,}\d", source)
        name_match = re.search(
            r"^\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})\s*$", source, re.MULTILINE
        )

        stack = [name for name, aliases in _STACK_ALIASES.items()
                 if any(alias in lowered for alias in aliases)]

        roles = [role for role, hints in _ROLE_HINTS.items()
                 if any(hint in lowered for hint in hints)]

        grade = next(
            (code for code, hints in _GRADE_HINTS if any(hint in lowered for hint in hints)),
            None,
        )

        experience = None
        exp_match = re.search(r"(\d{1,2})\s*(?:год|года|лет)", lowered)
        if exp_match:
            experience = int(exp_match.group(1))

        soft_skills = [hint for hint in _SOFT_HINTS if hint in lowered]

        return {
            "full_name": name_match.group(1).strip() if name_match else None,
            "contacts": {
                "email": email_match.group(0) if email_match else None,
                "phone": re.sub(r"\s+", " ", phone_match.group(0)).strip() if phone_match else None,
            },
            "stack": stack,
            "grade": grade,
            "roles": roles,
            "experience_years": experience,
            "soft_skills": soft_skills,
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
