"""Тесты LLM-провайдера Ollama: автоподбор модели, разбор ответа, обработка отказов.

Сеть не используется: HTTP подменяется транспортом `httpx.MockTransport`, поэтому
проверяется логика провайдера, а не наличие конкретной модели на машине.
"""

from __future__ import annotations

import httpx
import pytest

from app.providers.ollama import (
    OllamaLLMProvider,
    OllamaUnavailable,
    _strip_fence,
)


class _Recorder:
    """Записывает отправленные запросы и отдаёт заранее заданные ответы."""

    def __init__(
        self,
        *,
        tags: list[str] | None = None,
        chat: dict | None = None,
        embed: list | None = None,
        fail_with: Exception | None = None,
        fail_paths: set[str] | None = None,
    ):
        self.tags = tags or []
        self.chat = chat if chat is not None else {"message": {"content": "готово"}}
        self.embed = embed if embed is not None else [[0.1, 0.2]]
        self.requests: list[tuple[str, dict]] = []
        self.fail_with = fail_with
        # None — падают все запросы; иначе только указанные пути.
        self.fail_paths = fail_paths
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = {}
        if request.content:
            import json

            body = json.loads(request.content.decode())
        self.requests.append((request.url.path, body))
        if self.fail_with is not None and (self.fail_paths is None or request.url.path in self.fail_paths):
            raise self.fail_with
        if self.status != 200:
            return httpx.Response(self.status, json={"error": "boom"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": name} for name in self.tags]})
        if request.url.path == "/api/chat":
            return httpx.Response(200, json=self.chat)
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": self.embed})
        raise AssertionError(f"неожиданный путь: {request.url.path}")


def _provider(handler: _Recorder, **kwargs) -> OllamaLLMProvider:
    provider = OllamaLLMProvider(base_url="http://ollama.test", **kwargs)
    provider._client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=httpx.MockTransport(handler), base_url=provider.base_url
    )
    return provider


# --- снятие markdown-обёртки ------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ("```\n{}\n```", "{}"),
        ('{"a": 1}', '{"a": 1}'),
        ("  ```JSON  [1, 2] ```  ", "[1, 2]"),
    ],
)
def test_strip_fence_removes_markdown_wrapper(raw: str, expected: str) -> None:
    assert _strip_fence(raw) == expected


# --- доступность службы и список моделей ------------------------------------


async def test_available_models_reads_names() -> None:
    provider = _provider(_Recorder(tags=["gemma4:26b", "qwen3-embedding:0.6b"]))
    assert await provider._available_models() == ["gemma4:26b", "qwen3-embedding:0.6b"]


async def test_unreachable_service_raises_with_address() -> None:
    handler = _Recorder()
    handler.fail_with = httpx.ConnectError("connection refused")
    provider = _provider(handler)
    with pytest.raises(OllamaUnavailable) as error:
        await provider._available_models()
    assert "http://ollama.test" in str(error.value)


async def test_error_status_raises_unavailable() -> None:
    handler = _Recorder()
    handler.status = 500
    provider = _provider(handler)
    with pytest.raises(OllamaUnavailable):
        await provider._available_models()


async def test_no_installed_models_raises() -> None:
    provider = _provider(_Recorder(tags=[]))
    with pytest.raises(OllamaUnavailable) as error:
        await provider.resolve_model()
    assert "ни одной модели" in str(error.value)


# --- автоподбор модели -------------------------------------------------------


def test_explicit_model_is_used_when_present() -> None:
    assert OllamaLLMProvider._pick(["gemma4:26b"], ("gemma3",), "gemma4:26b", chat=True) == "gemma4:26b"


def test_model_without_tag_matches_installed_variant() -> None:
    """«gemma4» в настройке находит установленную «gemma4:12b-mlx»."""
    picked = OllamaLLMProvider._pick(["gemma4:12b-mlx"], ("gemma3",), "gemma4", chat=True)
    assert picked == "gemma4:12b-mlx"


def test_configured_model_absent_raises_with_available_list() -> None:
    with pytest.raises(OllamaUnavailable) as error:
        OllamaLLMProvider._pick(["llama3:8b"], ("gemma3",), "gemma4", chat=True)
    assert "llama3:8b" in str(error.value)


def test_chat_pick_skips_models_for_other_tasks() -> None:
    """Модели эмбеддингов и OCR не должны попадать в чат."""
    available = ["qwen3-embedding:0.6b", "deepseek-ocr", "gemma4:26b"]
    assert OllamaLLMProvider._pick(available, ("gemma4",), "", chat=True) == "gemma4:26b"


def test_pick_respects_preference_order() -> None:
    available = ["llama3:8b", "gemma3:4b"]
    assert OllamaLLMProvider._pick(available, ("gemma4", "gemma3", "llama3"), "", chat=True) == "gemma3:4b"


def test_pick_falls_back_to_first_available_when_nothing_matches() -> None:
    """Подходит любая открытая модель, даже вне списка предпочтений."""
    assert OllamaLLMProvider._pick(["my-own-llm:1b"], ("gemma4",), "", chat=True) == "my-own-llm:1b"


def test_pick_returns_none_without_candidates() -> None:
    assert OllamaLLMProvider._pick([], ("gemma4",), "", chat=True) is None


def test_pick_without_chat_restriction_keeps_embedding_models() -> None:
    available = ["qwen3-embedding:0.6b"]
    picked = OllamaLLMProvider._pick(available, ("qwen3-embedding",), "", chat=False)
    assert picked == "qwen3-embedding:0.6b"


async def test_resolve_model_is_cached() -> None:
    handler = _Recorder(tags=["gemma4:26b"])
    provider = _provider(handler)
    assert await provider.resolve_model() == "gemma4:26b"
    assert await provider.resolve_model() == "gemma4:26b"
    assert sum(1 for path, _ in handler.requests if path == "/api/tags") == 1


async def test_resolve_embed_model_raises_when_absent() -> None:
    provider = _provider(_Recorder(tags=[]))
    with pytest.raises(OllamaUnavailable):
        await provider.resolve_embed_model()


# --- генерация текста --------------------------------------------------------


async def test_complete_sends_system_format_and_thinking_flag() -> None:
    handler = _Recorder(tags=["gemma4:26b"], chat={"message": {"content": '{"ok": true}'}})
    provider = _provider(handler)
    schema = {"type": "object"}
    result = await provider.complete("привет", system="ты ассистент", json_schema=schema, max_tokens=128)

    assert result == '{"ok": true}'
    path, payload = next((p, b) for p, b in handler.requests if p == "/api/chat")
    assert payload["model"] == "gemma4:26b"
    assert payload["stream"] is False
    assert payload["think"] is False  # reasoning отключён: иначе ответ в разы медленнее
    assert payload["format"] == schema
    assert payload["options"] == {"temperature": 0, "num_predict": 128}
    assert payload["messages"][0] == {"role": "system", "content": "ты ассистент"}
    assert payload["messages"][-1] == {"role": "user", "content": "привет"}


async def test_complete_without_schema_returns_answer_as_is() -> None:
    handler = _Recorder(tags=["gemma4:26b"], chat={"message": {"content": "просто текст"}})
    provider = _provider(handler)
    assert await provider.complete("без схемы") == "просто текст"


async def test_complete_strips_fence_when_schema_requested() -> None:
    handler = _Recorder(tags=["gemma4:26b"], chat={"message": {"content": '```json\n{"a": 1}\n```'}})
    provider = _provider(handler)
    assert await provider.complete("запрос", json_schema={"type": "object"}) == '{"a": 1}'


async def test_empty_model_answer_raises() -> None:
    handler = _Recorder(tags=["gemma4:26b"], chat={"message": {"content": "   "}})
    provider = _provider(handler)
    with pytest.raises(OllamaUnavailable) as error:
        await provider.complete("запрос")
    assert "пустой ответ" in str(error.value)


async def test_complete_translates_http_failure() -> None:
    """Сбой самого запроса к модели (служба жива) переводится в OllamaUnavailable."""
    handler = _Recorder(tags=["gemma4:26b"], fail_with=httpx.ReadTimeout("timeout"), fail_paths={"/api/chat"})
    provider = _provider(handler)
    with pytest.raises(OllamaUnavailable) as error:
        await provider.complete("запрос")
    assert "не выполнен" in str(error.value)


async def test_complete_json_rejects_non_json_answer() -> None:
    handler = _Recorder(tags=["gemma4:26b"], chat={"message": {"content": "не json вовсе"}})
    provider = _provider(handler)
    with pytest.raises(OllamaUnavailable) as error:
        await provider.complete_json("запрос")
    assert "не-JSON" in str(error.value)


async def test_complete_json_rejects_json_array() -> None:
    handler = _Recorder(tags=["gemma4:26b"], chat={"message": {"content": "[1, 2, 3]"}})
    provider = _provider(handler)
    with pytest.raises(OllamaUnavailable) as error:
        await provider.complete_json("запрос")
    assert "JSON-объект" in str(error.value)


# --- эмбеддинги --------------------------------------------------------------


async def test_embed_sends_texts_and_returns_vectors() -> None:
    handler = _Recorder(tags=["qwen3-embedding:0.6b"], embed=[[0.1, 0.2], [0.3, 0.4]])
    provider = _provider(handler)
    vectors = await provider.embed(["первый", "второй"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    _, payload = next((p, b) for p, b in handler.requests if p == "/api/embed")
    assert payload == {"model": "qwen3-embedding:0.6b", "input": ["первый", "второй"]}


async def test_embed_rejects_vector_count_mismatch() -> None:
    handler = _Recorder(tags=["qwen3-embedding:0.6b"], embed=[[0.1]])
    provider = _provider(handler)
    with pytest.raises(OllamaUnavailable) as error:
        await provider.embed(["первый", "второй"])
    assert "не совпало" in str(error.value)


# --- состояние для интерфейса ------------------------------------------------


async def test_health_is_true_when_model_resolves() -> None:
    assert await _provider(_Recorder(tags=["gemma4:26b"])).health() is True


async def test_health_is_false_when_service_down() -> None:
    handler = _Recorder()
    handler.fail_with = httpx.ConnectError("refused")
    assert await _provider(handler).health() is False


async def test_describe_reports_available_model() -> None:
    info = await _provider(_Recorder(tags=["gemma4:26b"])).describe()
    assert info["available"] is True
    assert info["model"] == "gemma4:26b"
    assert info["think"] is False


async def test_describe_reports_reason_when_unavailable() -> None:
    handler = _Recorder()
    handler.fail_with = httpx.ConnectError("refused")
    info = await _provider(handler).describe()
    assert info["available"] is False
    assert info["model"] is None
    assert info["detail"]


# --- разбор резюме -----------------------------------------------------------


async def test_extract_resume_maps_fields_and_never_guesses_grade() -> None:
    answer = {
        "message": {
            "content": (
                '{"full_name": "Анна Ковалёва", "email": "anna@example.com", "phone": null,'
                ' "stack": ["Python", " ", "PostgreSQL"], "roles": ["Backend"],'
                ' "experience_years": 5, "soft_skills": ["командная работа", ""]}'
            )
        }
    }
    provider = _provider(_Recorder(tags=["gemma4:26b"], chat=answer))
    data = await provider.extract_resume("текст резюме")

    assert data["full_name"] == "Анна Ковалёва"
    assert data["contacts"] == {"email": "anna@example.com", "phone": None}
    assert data["stack"] == ["Python", "PostgreSQL"]  # пустые значения отброшены
    assert data["soft_skills"] == ["командная работа"]
    assert data["experience_years"] == 5
    assert data["source"] == "ollama"
    # Ключевое правило: грейд определяет тест, а не резюме
    assert data["grade"] is None


async def test_extract_resume_ignores_non_list_and_non_int_values() -> None:
    answer = {"message": {"content": '{"stack": "Python", "experience_years": "пять лет"}'}}
    provider = _provider(_Recorder(tags=["gemma4:26b"], chat=answer))
    data = await provider.extract_resume("текст")

    assert data["stack"] == []
    assert data["experience_years"] is None
    assert data["full_name"] is None
