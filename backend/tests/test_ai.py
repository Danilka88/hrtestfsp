"""Тесты ИИ-слоя: эндпоинты, откат на демо-данные, семантическое сопоставление.

Тесты выполняются в демо-режиме (`LLM_PROVIDER=mock`, задано в conftest) — они
проверяют, что платформа полностью работоспособна **без** установленной модели,
и что откат честно помечается признаком `degraded`.
"""

from __future__ import annotations

import pytest

from app.providers.mock import MockLLMProvider, detect_grade, detect_stack
from app.providers.ollama import OllamaLLMProvider, OllamaUnavailable
from app.providers.resilient import ResilientLLMProvider
from tests.conftest import register_and_verify

RESUME_TEXT = (
    "Меня зовут Иван Петров, работаю backend-разработчиком 5 лет. "
    "Пишу на Python, использую FastAPI, PostgreSQL, Docker и Redis."
)


async def _token(client, email: str, role: str) -> str:
    """Регистрация с подтверждением + вход: нужен access-токен для вызовов API."""
    await register_and_verify(client, email, role=role)
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "secret12345"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _employer(client) -> str:
    return await _token(client, "ai.emp@example.com", "employer")


async def _candidate(client) -> str:
    return await _token(client, "ai.cand@example.com", "candidate")


# --- состояние ИИ -----------------------------------------------------------


async def test_status_reports_demo_mode(client):
    token = await _employer(client)
    response = await client.get("/api/v1/ai/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "demo"
    assert body["degraded"] is True
    assert body["hint"], "подсказка для интерфейса должна быть заполнена"


# --- функции работодателя ---------------------------------------------------


async def test_need_draft_returns_valid_codes(client):
    token = await _employer(client)
    response = await client.post(
        "/api/v1/ai/need/draft",
        json={"brief": "нужен backend на Python FastAPI PostgreSQL, грейд senior"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    data = body["data"]
    # Специализация и грейд всегда пригодны для платформы, даже если модель их не дала
    assert data["specialization_code"] == "backend"
    assert data["grade"] in {"intern", "junior", "junior_plus", "middle", "senior", "lead"}
    assert "Python" in data["stack"]
    assert data["title"]


async def test_need_draft_normalizes_unknown_specialization(client):
    """Ответ с несуществующим кодом специализации не должен ломать подборку."""
    from app.services.ai import AIEngine

    engine = AIEngine()
    normalized = engine._normalize_need(
        {"title": "Роль", "stack": ["React", "TypeScript"], "specialization_code": "космос"}
    )
    assert normalized["specialization_code"] == "frontend"
    assert normalized["grade"] == "middle"


async def test_invitation_draft_contains_salary(client):
    token = await _employer(client)
    response = await client.post(
        "/api/v1/ai/invitation/draft",
        json={
            "company": "ООО «Тест»",
            "candidate_grade": "middle",
            "stack": ["Python", "Docker"],
            "salary_from": 250000,
            "salary_to": 320000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    message = response.json()["data"]["message"]
    assert "ООО «Тест»" in message
    assert "250" in message and "320" in message, "зарплата обязана попасть в текст"


async def test_task_draft_has_rubric(client):
    token = await _employer(client)
    response = await client.post(
        "/api/v1/ai/task/draft",
        json={"need_title": "Backend-разработчик", "stack": ["Python"], "grade": "middle"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["statement"]
    assert len(data["rubric"]) >= 2


# --- функции кандидата ------------------------------------------------------


async def test_profile_analyze_extracts_stack(client):
    token = await _candidate(client)
    response = await client.post(
        "/api/v1/ai/profile/analyze",
        json={"text": RESUME_TEXT},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert {"Python", "FastAPI", "PostgreSQL"} <= set(data["stack"])
    assert data["suggestions"], "кандидату нужны подсказки, что дополнить"


async def test_cover_letter_uses_real_overlap(client):
    token = await _candidate(client)
    response = await client.post(
        "/api/v1/ai/cover-letter",
        json={
            "vacancy_title": "Backend-разработчик",
            "company": "ООО «Тест»",
            "required_stack": ["Python", "FastAPI", "Kubernetes"],
            "candidate_stack": ["Python", "FastAPI"],
            "candidate_grade": "middle",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["letter"]
    assert set(data["matched"]) == {"Python", "FastAPI"}, "учитывается только реальное пересечение"


# --- семантическое сопоставление -------------------------------------------


async def test_semantic_scores_rank_related_text_higher(client):
    token = await _employer(client)
    response = await client.post(
        "/api/v1/ai/semantic/scores",
        json={
            "need_text": "Backend-разработчик Python FastAPI PostgreSQL",
            "candidate_texts": [
                "Python FastAPI PostgreSQL разработчик",
                "Дизайнер интерфейсов Figma",
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    scores = body["data"]["scores"]
    assert len(scores) == 2
    assert scores[0] > scores[1], "близкий профиль должен получить более высокий балл"
    assert body["data"]["method"]


async def test_semantic_scores_available_without_model(client):
    """Офлайн-режим обязан давать сопоставимый по смыслу сигнал (лексическая близость)."""
    token = await _employer(client)
    response = await client.post(
        "/api/v1/ai/semantic/scores",
        json={"need_text": "Docker Kubernetes", "candidate_texts": ["Docker Kubernetes", "верстка"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["data"]["scores"][0] > body["data"]["scores"][1]


# --- разграничение прав -----------------------------------------------------


async def test_candidate_cannot_draft_need(client):
    token = await _candidate(client)
    response = await client.post(
        "/api/v1/ai/need/draft",
        json={"brief": "нужен разработчик"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_employer_cannot_analyze_profile(client):
    token = await _employer(client)
    response = await client.post(
        "/api/v1/ai/profile/analyze",
        json={"text": RESUME_TEXT},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- устойчивость провайдера -----------------------------------------------


async def test_resilient_falls_back_when_model_unreachable():
    """Недоступная модель не должна ломать функцию: отдаются демо-данные с пометкой."""
    provider = ResilientLLMProvider(
        primary=OllamaLLMProvider(base_url="http://127.0.0.1:9", timeout=0.5),
        fallback=MockLLMProvider(),
    )
    data = await provider.extract_resume(RESUME_TEXT)
    assert provider.last_degraded is True
    assert {"Python", "FastAPI"} <= set(data["stack"])

    status = await provider.status()
    assert status["available"] is False
    assert status["degraded"] is True


async def test_ollama_provider_reports_unavailable():
    provider = OllamaLLMProvider(base_url="http://127.0.0.1:9", timeout=0.5)
    assert await provider.health() is False
    with pytest.raises(OllamaUnavailable):
        await provider.complete("привет")


async def test_mock_embeddings_are_deterministic_and_meaningful():
    provider = MockLLMProvider()
    first = await provider.embed(["Python Docker"])
    second = await provider.embed(["Python Docker"])
    assert first == second, "демо-векторы должны быть детерминированными"

    from app.services.ai import _cosine

    near = _cosine(
        (await provider.embed(["Python Docker"]))[0], (await provider.embed(["Python Docker FastAPI"]))[0]
    )
    far = _cosine((await provider.embed(["Python Docker"]))[0], (await provider.embed(["рисую макеты"]))[0])
    assert near > far, "лексическая близость должна разделять тексты"


def test_detection_helpers():
    assert "Python" in detect_stack("пишу на питоне")
    assert detect_grade("нужен senior разработчик") == "senior"
