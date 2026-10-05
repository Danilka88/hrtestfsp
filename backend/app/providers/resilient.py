"""Устойчивый LLM-провайдер: реальная модель с автоматическим откатом на демо-данные.

Зачем: демонстрация не должна зависеть от того, установлена ли модель на машине
судьи. При недоступности Ollama (служба не запущена, модель не скачана,
таймаут) провайдер молча переключается на детерминированные демо-данные и
**сообщает об этом** в ответе API полем `degraded`.

Поведение по режимам (`LLM_PROVIDER`):

* `auto`   — пробуем реальную модель, при неудаче отдаём демо-данные (по умолчанию);
* `ollama` — только реальная модель: ошибка, если недоступна (для отладки);
* `mock`   — только демо-данные, без обращений наружу (полностью офлайн).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.providers.base import ExternalIdentity  # noqa: F401 — реэкспорт контракта
from app.providers.mock import MockLLMProvider
from app.providers.ollama import OllamaLLMProvider, OllamaUnavailable

logger = logging.getLogger(__name__)


class LLMDisabled(RuntimeError):
    """Режим `ollama`: реальная модель недоступна, а демо-данные запрещены настройкой."""


class ResilientLLMProvider:
    """Обёртка «реальная модель → демо-данные» над контрактом `LLMProvider`."""

    name = "llm:auto"

    def __init__(
        self,
        primary: OllamaLLMProvider | None,
        fallback: MockLLMProvider,
        *,
        allow_fallback: bool = True,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.allow_fallback = allow_fallback
        # Последнее наблюдение о состоянии реальной модели: показываем его в UI.
        self.last_degraded = primary is None or not allow_fallback
        self.last_detail: str | None = None
        self.last_latency_ms: int | None = None
        self.last_source: str = "demo" if primary is None else "unresolved"

    # --- служебное ---------------------------------------------------------

    def _mark_success(self, source: str, started: float) -> None:
        self.last_degraded = False
        self.last_detail = None
        self.last_source = source
        self.last_latency_ms = int((time.perf_counter() - started) * 1000)

    def _mark_degraded(self, detail: str, started: float) -> None:
        self.last_degraded = True
        self.last_detail = detail
        self.last_source = "demo"
        self.last_latency_ms = int((time.perf_counter() - started) * 1000)
        logger.warning("LLM недоступна, используются демо-данные: %s", detail)

    async def status(self) -> dict[str, Any]:
        """Состояние LLM для интерфейса: какой провайдер, модель, деградация."""
        if self.primary is None:
            return {
                "provider": "demo",
                "available": False,
                "degraded": True,
                "model": None,
                "detail": "режим mock: работают только демо-данные",
            }
        info = await self.primary.describe()
        return {
            "provider": "ollama" if info.get("available") else "demo",
            "available": bool(info.get("available")),
            "degraded": not info.get("available"),
            "model": info.get("model"),
            "base_url": info.get("base_url"),
            "think": info.get("think"),
            "detail": info.get("detail"),
        }

    async def health(self) -> bool:
        # Провайдер работоспособен всегда: при недоступности модели есть демо-данные.
        return True

    # --- контракт LLMProvider ---------------------------------------------

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_schema: dict | None = None,
        max_tokens: int = 512,
    ) -> str:
        started = time.perf_counter()
        if self.primary is not None:
            try:
                text = await self.primary.complete(
                    prompt, system=system, json_schema=json_schema, max_tokens=max_tokens
                )
                self._mark_success(f"ollama:{await self.primary.resolve_model()}", started)
                return text
            except OllamaUnavailable as exc:
                self._mark_degraded(str(exc), started)
                if not self.allow_fallback:
                    raise LLMDisabled(str(exc)) from exc
        return await self.fallback.complete(
            prompt, system=system, json_schema=json_schema, max_tokens=max_tokens
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        started = time.perf_counter()
        if self.primary is not None:
            try:
                vectors = await self.primary.embed(texts)
                self._mark_success(f"ollama:{await self.primary.resolve_embed_model()}", started)
                return vectors
            except OllamaUnavailable as exc:
                self._mark_degraded(str(exc), started)
                if not self.allow_fallback:
                    raise LLMDisabled(str(exc)) from exc
        return await self.fallback.embed(texts)

    async def extract_resume(self, text: str) -> dict:
        started = time.perf_counter()
        if self.primary is not None:
            try:
                data = await self.primary.extract_resume(text)
                self._mark_success(f"ollama:{await self.primary.resolve_model()}", started)
                return data
            except OllamaUnavailable as exc:
                self._mark_degraded(str(exc), started)
                if not self.allow_fallback:
                    raise LLMDisabled(str(exc)) from exc
        return await self.fallback.extract_resume(text)


def build_llm_provider() -> ResilientLLMProvider:
    """Собирает провайдера по настройке `LLM_PROVIDER`."""
    from app.core.config import get_settings

    mode = (get_settings().llm_provider or "auto").lower()
    fallback = MockLLMProvider()
    if mode == "mock":
        return ResilientLLMProvider(primary=None, fallback=fallback)
    return ResilientLLMProvider(
        primary=OllamaLLMProvider(),
        fallback=fallback,
        allow_fallback=mode != "ollama",
    )
