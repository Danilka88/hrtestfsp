"""Реальный LLM-провайдер: локальная открытая модель через Ollama.

Почему локальная модель, а не внешний API:

* **152-ФЗ.** Тексты резюме и профилей кандидатов не покидают контур — нет
  передачи персональных данных третьим лицам и внешних ключей.
* **Любая открытая модель.** Код не привязан к конкретной модели: имя задаётся
  настройкой `OLLAMA_MODEL`, а при пустом значении модель выбирается из уже
  скачанных по порядку предпочтения (gemma4 → gemma3 → qwen3 → llama3 …).
  Поддерживаются модели с лицензией Apache 2.0 (Gemma 4, Qwen), MIT и др.
* **Структурированный вывод.** Ollama умеет гарантировать валидный JSON
  (`format`), поэтому разбор ответа не строится на регулярных выражениях.

Особенности Gemma 4, проверенные замерами на Apple Silicon (M-серия):

* включённый reasoning замедляет короткие задачи примерно в 40 раз
  (9.8 с против 0.25 с на одном и том же запросе), поэтому `think=False`
  выставлен по умолчанию для задач извлечения и генерации черновиков;
* без явного `format=json` модель оборачивает JSON в ```-блок, поэтому
  `_strip_fence` снимает обёртку — иначе `json.loads` падает.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Порядок предпочтения при автоподборе. Список лишь задаёт приоритет —
# подойдёт любая открытая модель, установленная в Ollama.
CHAT_MODEL_PREFERENCE = (
    "gemma4",
    "gemma3",
    "qwen3",
    "qwen2.5",
    "llama3",
    "mistral",
    "phi",
    "deepseek",
)

EMBED_MODEL_PREFERENCE = (
    "qwen3-embedding",
    "bge-m3",
    "bge",
    "e5",
    "nomic-embed",
    "all-minilm",
)

# Модели для других задач — исключаются из автоподбора чата.
NON_CHAT_MARKERS = ("embedding", "embed", "ocr", "whisper", "tts", "rerank")

FENCE_RE = re.compile(r"^\s*```(?:json|json5)?\s*|\s*```\s*$", re.IGNORECASE)


class OllamaUnavailable(RuntimeError):
    """Ollama недоступна: служба не запущена, таймаут или нет подходящей модели."""


def _strip_fence(text: str) -> str:
    """Снимает markdown-обёртку ```json … ``` вокруг ответа модели."""
    cleaned = FENCE_RE.sub("", text.strip())
    return cleaned.strip()


class OllamaLLMProvider:
    """LLM на локальной модели через HTTP API Ollama."""

    name = "llm:ollama"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        embed_model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._configured_model = settings.ollama_model if model is None else model
        self._configured_embed = settings.ollama_embed_model if embed_model is None else embed_model
        self.timeout = timeout or settings.llm_timeout_seconds
        self.think = settings.llm_think
        self._model: str | None = None
        self._embed_model: str | None = None

    # --- служебное ---------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def _available_models(self) -> list[str]:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
        except httpx.HTTPError as exc:  # сеть, таймаут, 5xx
            raise OllamaUnavailable(f"Ollama недоступна по адресу {self.base_url}: {exc}") from exc
        return [item["name"] for item in response.json().get("models", [])]

    @staticmethod
    def _pick(available: list[str], preferred: tuple[str, ...], configured: str, *, chat: bool) -> str | None:
        """Выбирает модель: сначала явно заданную, затем по порядку предпочтения."""
        if configured:
            if configured in available:
                return configured
            # допускаем запись без тега: "gemma4" → "gemma4:12b-mlx"
            for name in available:
                if name.split(":")[0] == configured.split(":")[0]:
                    return name
            raise OllamaUnavailable(
                f"Модель '{configured}' не найдена в Ollama. Доступны: {', '.join(available) or '—'}"
            )

        candidates = available
        if chat:
            candidates = [name for name in available if not any(m in name.lower() for m in NON_CHAT_MARKERS)]
        for prefix in preferred:
            for name in candidates:
                if name.lower().startswith(prefix):
                    return name
        return candidates[0] if candidates else None

    async def resolve_model(self, *, force: bool = False) -> str:
        """Имя используемой чат-модели (кэшируется, пока служба отвечает)."""
        if self._model is None or force:
            available = await self._available_models()
            if not available:
                raise OllamaUnavailable("В Ollama не загружено ни одной модели")
            picked = self._pick(available, CHAT_MODEL_PREFERENCE, self._configured_model, chat=True)
            if picked is None:
                raise OllamaUnavailable("Не найдено модели, пригодной для генерации текста")
            self._model = picked
        return self._model

    async def resolve_embed_model(self, *, force: bool = False) -> str:
        if self._embed_model is None or force:
            available = await self._available_models()
            picked = self._pick(available, EMBED_MODEL_PREFERENCE, self._configured_embed, chat=False)
            if picked is None:
                raise OllamaUnavailable("Не найдено модели эмбеддингов")
            self._embed_model = picked
        return self._embed_model

    # --- контракт провайдера ----------------------------------------------

    async def health(self) -> bool:
        try:
            await self.resolve_model()
        except OllamaUnavailable:
            return False
        return True

    async def describe(self) -> dict[str, Any]:
        """Состояние провайдера для интерфейса: адрес, модель, доступность."""
        try:
            model = await self.resolve_model()
        except OllamaUnavailable as exc:
            return {"available": False, "base_url": self.base_url, "model": None, "detail": str(exc)}
        return {
            "available": True,
            "base_url": self.base_url,
            "model": model,
            "think": self.think,
            "detail": "локальная модель доступна",
        }

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_schema: dict | None = None,
        max_tokens: int = 512,
    ) -> str:
        """Один запрос к модели. При `json_schema` ответ гарантированно валиден как JSON."""
        model = await self.resolve_model()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "options": {"temperature": 0, "num_predict": max_tokens},
        }
        if json_schema is not None:
            # Структурированный вывод: модель обязана вернуть валидный JSON.
            payload["format"] = json_schema

        try:
            async with self._client() as client:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(f"Запрос к модели не выполнен: {exc}") from exc

        content = response.json().get("message", {}).get("content", "")
        if not content.strip():
            raise OllamaUnavailable("Модель вернула пустой ответ")
        return content if json_schema is None else _strip_fence(content)

    async def complete_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_schema: dict | None = None,
        max_tokens: int = 512,
    ) -> dict:
        raw = await self.complete(
            prompt,
            system=system,
            json_schema=json_schema or {"type": "object"},
            max_tokens=max_tokens,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaUnavailable(f"Модель вернула не-JSON: {raw[:200]}") from exc
        if not isinstance(data, dict):
            raise OllamaUnavailable("Ожидался JSON-объект")
        return data

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = await self.resolve_embed_model()
        try:
            async with self._client() as client:
                response = await client.post("/api/embed", json={"model": model, "input": texts})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(f"Эмбеддинги недоступны: {exc}") from exc
        embeddings = response.json().get("embeddings", [])
        if len(embeddings) != len(texts):
            raise OllamaUnavailable("Число векторов не совпало с числом текстов")
        return embeddings

    # --- прикладной разбор резюме -----------------------------------------

    RESUME_SCHEMA = {
        "type": "object",
        "properties": {
            "full_name": {"type": ["string", "null"]},
            "email": {"type": ["string", "null"]},
            "phone": {"type": ["string", "null"]},
            "stack": {"type": "array", "items": {"type": "string"}},
            "roles": {"type": "array", "items": {"type": "string"}},
            "experience_years": {"type": ["integer", "null"]},
            "soft_skills": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["stack"],
    }

    async def extract_resume(self, text: str) -> dict:
        """Извлекает поля профиля из текста резюме. Возвращает ту же форму, что mock."""
        system = (
            "Ты извлекаешь факты из резюме ИТ-специалиста. Возвращай только то, что "
            "явно есть в тексте. Не додумывай отсутствующие данные: ставь null или "
            "пустой список. Стек — короткие названия технологий (Python, PostgreSQL). "
            "Отвечай по-русски."
        )
        prompt = f"Извлеки поля профиля из текста резюме:\n\n{text[:6000]}"
        data = await self.complete_json(prompt, system=system, json_schema=self.RESUME_SCHEMA, max_tokens=700)

        def _list(value: Any) -> list[str]:
            if not isinstance(value, list):
                return []
            return [str(item).strip() for item in value if str(item).strip()]

        return {
            "full_name": data.get("full_name") or None,
            "contacts": {"email": data.get("email") or None, "phone": data.get("phone") or None},
            "stack": _list(data.get("stack")),
            "grade": None,  # грейд не берём из резюме: его определяет тест
            "roles": _list(data.get("roles")),
            "experience_years": data.get("experience_years")
            if isinstance(data.get("experience_years"), int)
            else None,
            "soft_skills": _list(data.get("soft_skills")),
            "source": "ollama",
        }
