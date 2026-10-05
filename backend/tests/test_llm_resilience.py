"""Тесты устойчивости LLM-слоя: реальная модель с откатом на демо-данные.

Это ключевая гарантия демонстрации: если модель недоступна (на машине судьи её
нет, служба не запущена, таймаут), платформа отвечает детерминированными
демо-данными и **сообщает** об этом полем `degraded`, а не падает.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import get_settings
from app.providers.mock import MockLLMProvider
from app.providers.ollama import OllamaLLMProvider, OllamaUnavailable
from app.providers.resilient import (
    LLMDisabled,
    ResilientLLMProvider,
    build_llm_provider,
)


class _StubModel:
    """Заглушка реальной модели: отвечает либо падает — по флагу `fail`."""

    def __init__(self, *, fail: bool = False, model: str = "gemma4:26b") -> None:
        self.fail = fail
        self.model = model
        self.calls: list[str] = []

    def _touch(self, what: str) -> None:
        self.calls.append(what)
        if self.fail:
            raise OllamaUnavailable(f"служба недоступна ({what})")

    async def complete(self, prompt, *, system=None, json_schema=None, max_tokens=512) -> str:
        self._touch("complete")
        return "ответ реальной модели"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._touch("embed")
        return [[1.0, 0.0] for _ in texts]

    async def extract_resume(self, text: str) -> dict:
        self._touch("extract_resume")
        return {"full_name": "Из модели", "stack": ["Python"], "source": "ollama"}

    async def resolve_model(self, *, force: bool = False) -> str:
        return self.model

    async def resolve_embed_model(self, *, force: bool = False) -> str:
        return "qwen3-embedding:0.6b"

    async def describe(self) -> dict:
        if self.fail:
            return {"available": False, "model": None, "base_url": "http://x", "detail": "нет связи"}
        return {
            "available": True,
            "model": self.model,
            "base_url": "http://x",
            "think": False,
            "detail": "локальная модель доступна",
        }


def _provider(primary: _StubModel | None, *, allow_fallback: bool = True) -> ResilientLLMProvider:
    return ResilientLLMProvider(
        primary=primary,  # type: ignore[arg-type] — заглушка реализует тот же контракт
        fallback=MockLLMProvider(),
        allow_fallback=allow_fallback,
    )


# --- генерация текста --------------------------------------------------------


async def test_successful_generation_uses_real_model() -> None:
    stub = _StubModel()
    provider = _provider(stub)
    text = await provider.complete("привет")

    assert text == "ответ реальной модели"
    assert provider.last_degraded is False
    assert provider.last_source == "ollama:gemma4:26b"
    assert provider.last_detail is None
    assert isinstance(provider.last_latency_ms, int)


async def test_unreachable_model_falls_back_to_demo_data() -> None:
    """Падение модели не ломает ответ: подставляются демо-данные."""
    provider = _provider(_StubModel(fail=True))
    text = await provider.complete("собери потребность", json_schema={"type": "object"})

    assert json.loads(text) == {}, "демо-режим обязан вернуть валидный JSON"
    assert provider.last_degraded is True
    assert provider.last_source == "demo"
    assert "недоступна" in (provider.last_detail or "")


async def test_modes_without_fallback_raise_instead_of_demo_data() -> None:
    """Режим `ollama`: демо-данные запрещены — ошибка честнее подмены."""
    provider = _provider(_StubModel(fail=True), allow_fallback=False)
    with pytest.raises(LLMDisabled):
        await provider.complete("запрос")
    assert provider.last_degraded is True


async def test_no_primary_always_uses_demo_data() -> None:
    provider = _provider(None)
    assert json.loads(await provider.complete("что угодно", json_schema={"type": "object"})) == {}
    assert provider.last_degraded is True
    assert provider.last_source == "demo"


async def test_demo_provider_does_not_invent_free_text() -> None:
    """Контракт демо-провайдера: осмысленный текст делает сервисный слой.

    Провайдер без модели возвращает пустую строку, а не выдуманный текст; черновики
    для интерфейса собираются в `app/services/ai.py` из демо-данных (см. test_ai.py).
    """
    provider = _provider(None)
    assert await provider.complete("свободный текст") == ""


# --- эмбеддинги --------------------------------------------------------------


async def test_embeddings_from_real_model() -> None:
    provider = _provider(_StubModel())
    vectors = await provider.embed(["первый", "второй"])

    assert vectors == [[1.0, 0.0], [1.0, 0.0]]
    assert provider.last_source == "ollama:qwen3-embedding:0.6b"
    assert provider.last_degraded is False


async def test_embeddings_fall_back_and_are_usable() -> None:
    provider = _provider(_StubModel(fail=True))
    vectors = await provider.embed(["первый", "второй"])

    assert len(vectors) == 2
    assert all(isinstance(value, float) for value in vectors[0])
    assert provider.last_degraded is True


async def test_embeddings_raise_without_fallback_mode() -> None:
    provider = _provider(_StubModel(fail=True), allow_fallback=False)
    with pytest.raises(LLMDisabled):
        await provider.embed(["текст"])


# --- разбор резюме -----------------------------------------------------------


async def test_resume_parsing_from_real_model() -> None:
    provider = _provider(_StubModel())
    data = await provider.extract_resume("текст")

    assert data["source"] == "ollama"
    assert provider.last_source == "ollama:gemma4:26b"


async def test_resume_parsing_falls_back_without_model() -> None:
    provider = _provider(_StubModel(fail=True))
    data = await provider.extract_resume("Анна Ковалёва, Python, PostgreSQL")

    assert data, "демо-разбор должен вернуть данные"
    assert provider.last_degraded is True


async def test_resume_parsing_raises_without_fallback_mode() -> None:
    provider = _provider(_StubModel(fail=True), allow_fallback=False)
    with pytest.raises(LLMDisabled):
        await provider.extract_resume("текст")


# --- состояние, видимое в интерфейсе ----------------------------------------


async def test_health_is_always_true() -> None:
    """Слой работоспособен всегда: при недоступности модели есть демо-данные."""
    assert await _provider(None).health() is True
    assert await _provider(_StubModel(fail=True)).health() is True


async def test_status_in_mock_mode_reports_demo() -> None:
    status = await _provider(None).status()

    assert status["provider"] == "demo"
    assert status["available"] is False
    assert status["degraded"] is True
    assert status["model"] is None


async def test_status_reports_real_model_when_available() -> None:
    status = await _provider(_StubModel()).status()

    assert status["provider"] == "ollama"
    assert status["available"] is True
    assert status["degraded"] is False
    assert status["model"] == "gemma4:26b"


async def test_status_reports_degradation_when_model_is_down() -> None:
    status = await _provider(_StubModel(fail=True)).status()

    assert status["provider"] == "demo"
    assert status["available"] is False
    assert status["degraded"] is True
    assert status["detail"] == "нет связи"


# --- сборка провайдера по настройке ----------------------------------------


@pytest.fixture
def build_for_mode(monkeypatch):
    """Собирает провайдера для заданного режима `LLM_PROVIDER`."""

    def build(mode: str) -> ResilientLLMProvider:
        monkeypatch.setenv("LLM_PROVIDER", mode)
        get_settings.cache_clear()
        return build_llm_provider()

    yield build
    get_settings.cache_clear()


def test_mock_mode_has_no_external_model(build_for_mode) -> None:
    provider = build_for_mode("mock")
    assert provider.primary is None
    assert provider.name == "llm:auto"


def test_auto_mode_uses_ollama_with_fallback(build_for_mode) -> None:
    provider = build_for_mode("auto")
    assert isinstance(provider.primary, OllamaLLMProvider)
    assert provider.allow_fallback is True


def test_ollama_mode_forbids_demo_fallback(build_for_mode) -> None:
    provider = build_for_mode("ollama")
    assert isinstance(provider.primary, OllamaLLMProvider)
    assert provider.allow_fallback is False


def test_unknown_mode_behaves_like_auto(build_for_mode) -> None:
    """Опечатка в настройке не должна оставлять платформу без модели."""
    provider = build_for_mode("olama")
    assert isinstance(provider.primary, OllamaLLMProvider)
    assert provider.allow_fallback is True
