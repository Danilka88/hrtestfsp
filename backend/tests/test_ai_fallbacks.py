"""Тесты отказоустойчивости ИИ-слоя и объяснения подборки.

Главное правило: любая ошибка модели не должна ломать пользовательский сценарий —
интерфейс получает подготовленные демо-данные с пометкой «демо-режим» (и это
проверяется здесь). Разбор ответа модели устойчив к markdown-обёртке и к тексту
вокруг JSON.
"""

from __future__ import annotations

import logging

from httpx import AsyncClient

import app.services.ai as ai_service
from app.services.ai import AIError, _cosine, _parse_json
from tests.test_employers import _auth, _bank, _employer_token

# --- разбор ответа модели ----------------------------------------------------


def test_parse_json_accepts_plain_object() -> None:
    assert _parse_json('{"stack": ["Python"]}') == {"stack": ["Python"]}


def test_parse_json_strips_markdown_fence() -> None:
    """Gemma оборачивает JSON в ```-блок, если не задан формат ответа."""
    assert _parse_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_parse_json_extracts_object_from_surrounding_text() -> None:
    raw = 'Конечно! Вот результат: {"grade": "middle"} — надеюсь, подойдёт.'
    assert _parse_json(raw) == {"grade": "middle"}


def test_parse_json_rejects_empty_and_placeholder_answers() -> None:
    """Пустой ответ и `{}` — это отсутствие данных, а не результат."""
    assert _parse_json("") is None
    assert _parse_json("   ") is None
    assert _parse_json("{}") is None


def test_parse_json_rejects_non_object_json() -> None:
    assert _parse_json("[1, 2, 3]") is None
    assert _parse_json('"просто строка"') is None


def test_parse_json_rejects_garbage() -> None:
    assert _parse_json("никакого json здесь нет") is None


# --- косинус для семантического сопоставления --------------------------------


def test_cosine_requires_vectors_of_same_length() -> None:
    assert _cosine([1.0, 0.0], [1.0]) == 0.0


def test_cosine_of_empty_vector_is_zero() -> None:
    assert _cosine([], []) == 0.0


def test_cosine_of_identical_vectors_is_one() -> None:
    assert _cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0


# --- доменная ошибка ---------------------------------------------------------


def test_ai_error_carries_status_and_detail() -> None:
    error = AIError(404, "Кандидат не найден")
    assert error.status_code == 404
    assert error.detail == "Кандидат не найден"
    assert str(error) == "Кандидат не найден"


# --- движок: отказ модели не ломает сценарий ---------------------------------


class _BrokenProvider:
    """Модель, которая падает на любом запросе."""

    last_degraded = False
    last_source = "ollama:broken"

    async def complete(self, prompt, **kwargs):
        raise RuntimeError("модель упала")


class _WorkingProvider:
    """Модель, отвечающая валидным JSON."""

    last_degraded = False
    last_source = "ollama:gemma4:26b"

    def __init__(self, answer: str) -> None:
        self.answer = answer

    async def complete(self, prompt, **kwargs):
        return self.answer


async def test_engine_returns_demo_data_when_provider_raises(monkeypatch, caplog) -> None:
    """Ошибка модели логируется, а сценарий продолжается на демо-данных."""
    monkeypatch.setattr(ai_service, "get_llm", lambda: _BrokenProvider())

    with caplog.at_level(logging.WARNING, logger="app.services.ai"):
        result = await ai_service.get_ai()._json(
            "запрос", system="система", schema={"type": "object"}, demo=lambda: {"draft": "демо"}
        )

    assert result.degraded is True
    assert result.provider == "demo"
    assert result.data == {"draft": "демо"}
    assert result.note, "пометка о демо-режиме обязательна для интерфейса"
    assert "ИИ недоступен" in caplog.text


async def test_engine_uses_model_answer_when_it_is_valid(monkeypatch) -> None:
    monkeypatch.setattr(ai_service, "get_llm", lambda: _WorkingProvider('{"draft": "от модели"}'))

    result = await ai_service.get_ai()._json(
        "запрос", system="система", schema={"type": "object"}, demo=lambda: {"draft": "демо"}
    )

    assert result.degraded is False
    assert result.provider == "ollama:gemma4:26b"
    assert result.data == {"draft": "от модели"}


async def test_engine_falls_back_when_answer_is_unparseable(monkeypatch) -> None:
    """Неразборчивый ответ модели трактуется как недоступность, а не как данные."""
    monkeypatch.setattr(ai_service, "get_llm", lambda: _WorkingProvider("болтовня без JSON"))

    result = await ai_service.get_ai()._json(
        "запрос", system="система", schema={"type": "object"}, demo=lambda: {"draft": "демо"}
    )

    assert result.degraded is True
    assert result.data == {"draft": "демо"}


# --- состояние ИИ в интерфейсе -----------------------------------------------


async def test_status_reports_working_model_without_degradation(client: AsyncClient, monkeypatch) -> None:
    from tests.conftest import register_and_verify

    await register_and_verify(client, "ai-status@example.com")
    token = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "ai-status@example.com", "password": "secret12345"},
        )
    ).json()["access_token"]
    """Когда модель доступна, подсказка говорит об этом, а не о демо-режиме."""

    class _Engine:
        async def status(self) -> dict:
            return {
                "provider": "ollama",
                "available": True,
                "degraded": False,
                "model": "gemma4:26b",
                "base_url": "http://host.docker.internal:11434",
                "think": False,
                "detail": "локальная модель доступна",
            }

    monkeypatch.setattr("app.api.v1.endpoints.ai.get_ai", lambda: _Engine())

    response = await client.get("/api/v1/ai/status", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert "локальная модель" in body["hint"]
    assert "демо" not in body["hint"].lower()


# --- объяснение попадания в подборку -----------------------------------------


async def _selection_with_candidates(client: AsyncClient, db_factory, email: str) -> dict:
    await _bank(client, db_factory)
    token = await _employer_token(client, email)
    await client.put(
        "/api/v1/employers/me/profile",
        json={"company_name": "ООО Тест", "contact_email": "hr@test.ru"},
        headers=_auth(token),
    )
    response = await client.post(
        "/api/v1/employers/me/needs",
        json={
            "title": "Backend-разработчик",
            "specialization_code": "backend",
            "grade": "middle",
            "stack": ["Python", "Docker"],
            "salary_from": 200000,
            "salary_to": 300000,
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return {"token": token, "selection": response.json()}


async def test_explain_match_returns_text_and_keeps_missing_list(client: AsyncClient, db_factory) -> None:
    ctx = await _selection_with_candidates(client, db_factory, "ai-explain@example.com")
    card = ctx["selection"]["candidates"][0]

    response = await client.post(
        "/api/v1/ai/match/explain",
        json={"selection_id": ctx["selection"]["id"], "candidate_reference": card["reference"]},
        headers=_auth(ctx["token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["summary"], "объяснение должно быть непустым"
    assert body["data"]["points"], "к объяснению прилагаются пункты"
    # Список «нет данных» не теряется при объяснении словами
    assert "missing" in body["data"]
    assert body["provider"] in {"demo", "ollama"} or body["degraded"] is True


async def test_explain_match_rejects_candidate_outside_selection(client: AsyncClient, db_factory) -> None:
    ctx = await _selection_with_candidates(client, db_factory, "ai-explain-404@example.com")

    response = await client.post(
        "/api/v1/ai/match/explain",
        json={"selection_id": ctx["selection"]["id"], "candidate_reference": "cand-00000000"},
        headers=_auth(ctx["token"]),
    )
    assert response.status_code == 404
    assert "не найден" in response.json()["detail"]


# --- подсказки при разборе профиля ------------------------------------------


async def test_analyze_profile_suggests_filling_missing_fields(client: AsyncClient) -> None:
    """Пустой профиль: интерфейс получает конкретные подсказки, а не пустой экран."""
    from tests.conftest import register_and_verify

    await register_and_verify(client, "ai-analyze@example.com")
    token = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "ai-analyze@example.com", "password": "secret12345"},
        )
    ).json()["access_token"]

    response = await client.post(
        "/api/v1/ai/profile/analyze",
        json={"text": "Резюме пока не заполнено, хочу работать в ИТ-сфере."},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    suggestions = " ".join(body["data"]["suggestions"])
    assert "стек" in suggestions.lower()
    assert "роли" in suggestions.lower()
    assert "тест" in suggestions.lower(), "нужно пояснять, что грейд присваивает тест"
