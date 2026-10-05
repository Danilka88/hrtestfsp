"""Mock-реализации провайдеров (режим по умолчанию).

Позволяют демонстрировать сквозной сценарий без интернета и платных сервисов.
Разбор резюме детерминированный, по словарю технологий: этого достаточно для
демо и тестов, а реальный LLM подключается за тем же интерфейсом.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re

from app.providers.base import FspAchievement

logger = logging.getLogger(__name__)

# Размерность офлайн-векторов. Согласована с демо-эмбеддингами: позволяет
# сравнивать векторы, полученные хеш-векторизатором, между собой.
HASH_VECTOR_DIM = 256
_WORD_RE = re.compile(r"[a-zа-яё0-9+#.]+", re.IGNORECASE)


def _hash_vector(text: str, dim: int = HASH_VECTOR_DIM) -> list[float]:
    """Хеширующий мешок слов (feature hashing) — офлайн-замена эмбеддингов.

    Каждый токен детерминированно отображается в координату вектора, значение
    накапливается по частоте и нормируется. Косинус таких векторов отражает
    лексическое пересечение: совпавшие термины (Python, PostgreSQL) сближают
    тексты, что для сопоставления стека даёт тот же знак сигнала, что и
    настоящие эмбеддинги, но без модели.
    """
    vector = [0.0] * dim
    tokens = _WORD_RE.findall((text or "").lower())
    for token in tokens:
        if len(token) < 2:
            continue
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
        index = int.from_bytes(digest, "big") % dim
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


# Словарь технологий. Поиск идёт по подстроке в тексте, приведённом к нижнему регистру.
_STACK_ALIASES: dict[str, list[str]] = {
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

_ROLE_HINTS: dict[str, list[str]] = {
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

_SOFT_HINTS = [
    "команд",
    "коммуника",
    "ответствен",
    "ментор",
    "наставни",
    "лидер",
    "самостоятельн",
    "инициатив",
]


def detect_stack(text: str) -> list[str]:
    """Технологии, найденные в тексте (общий словарь демо-режима)."""
    lowered = (text or "").lower()
    return [name for name, aliases in _STACK_ALIASES.items() if any(a in lowered for a in aliases)]


def detect_roles(text: str) -> list[str]:
    """Роли, найденные в тексте по словарю подсказок."""
    lowered = (text or "").lower()
    return [role for role, hints in _ROLE_HINTS.items() if any(hint in lowered for hint in hints)]


def detect_grade(text: str) -> str | None:
    """Грейд, упомянутый в тексте (intern … lead)."""
    lowered = (text or "").lower()
    return next((code for code, hints in _GRADE_HINTS if any(hint in lowered for hint in hints)), None)


class MockLLMProvider:
    """Демо-реализация LLM: детерминированные ответы без обращений наружу.

    Используется как запасной вариант, когда локальная модель недоступна
    (например, на машине судьи без Ollama). Прикладные демо-ответы живут в
    `app/services/ai.py` — там, где известна конкретная задача.
    """

    name = "llm:mock"

    async def health(self) -> bool:
        return True

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_schema: dict | None = None,
        max_tokens: int = 512,
    ) -> str:
        """Детерминированная заглушка: без модели осмысленный текст не генерируется."""
        if json_schema is not None:
            return "{}"
        return ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Офлайн-векторизация: хеширующий мешок слов.

        Это не нейросетевые эмбеддинги, а честная лексическая близость —
        работает без модели и даёт сопоставимый по смыслу сигнал на терминах
        (совпавшие технологии повышают косинус).
        """
        return [_hash_vector(text) for text in texts]

    async def extract_resume(self, text: str) -> dict:
        """Детерминированный разбор резюме без внешних вызовов.

        Возвращаются только реально найденные в тексте значения: отсутствующие
        поля остаются пустыми и не додумываются.
        """
        source = text or ""
        lowered = source.lower()

        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", source)
        phone_match = re.search(r"\+?\d[\d\s\-()]{9,}\d", source)
        name_match = re.search(r"^\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})\s*$", source, re.MULTILINE)

        stack = [
            name for name, aliases in _STACK_ALIASES.items() if any(alias in lowered for alias in aliases)
        ]

        roles = [role for role, hints in _ROLE_HINTS.items() if any(hint in lowered for hint in hints)]

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

    async def fetch_achievements(self, fsp_id: str) -> list[FspAchievement]:
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
