"""Тесты механики тестирования и категоризации."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.testing import Item
from app.services.item_factory import generate_items
from app.services.testing import GRADE_ORDER
from tests.conftest import register_and_verify

# --- Юнит-уровень: параметрическая генерация --------------------------------


def test_generation_is_deterministic_for_same_seed() -> None:
    first = generate_items(seed=1)
    second = generate_items(seed=1)
    assert [i.payload["question"] for i in first] == [i.payload["question"] for i in second]


def test_generated_items_are_well_formed() -> None:
    items = generate_items(seed=42)
    assert items, "банк заданий не должен быть пустым"
    for item in items:
        payload = item.payload
        assert payload["options"], "у задания должны быть варианты ответа"
        assert 0 <= payload["correct_index"] < len(payload["options"])
        assert len(set(payload["options"])) == len(payload["options"]), "варианты не должны повторяться"


def test_generation_covers_difficulty_range() -> None:
    difficulties = [i.difficulty for i in generate_items(seed=7)]
    assert min(difficulties) < -0.5
    assert max(difficulties) > 1.0


def test_templates_produce_different_questions() -> None:
    questions = {i.payload["question"] for i in generate_items(seed=11)}
    assert len(questions) >= 10, "формулировки должны различаться между вариантами"


# --- Интеграционный уровень: API --------------------------------------------


async def _login(client: AsyncClient, email: str, role: str = "candidate") -> str:
    await register_and_verify(client, email, role=role)
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "secret12345"})
    return response.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _answer_key(db_factory) -> dict[str, int]:
    """Правильные ответы банка — известны только тесту."""
    async with db_factory() as session:
        items = (await session.execute(select(Item))).scalars().all()
        return {i.id: i.payload["correct_index"] for i in items}


async def _run_test(
    client: AsyncClient, token: str, db_factory, *, correct: bool, target_grade: str = "middle"
) -> dict:
    """Проходит тест целиком, отвечая верно или неверно, и возвращает результат."""
    answers = await _answer_key(db_factory)
    start = await client.post(
        "/api/v1/testing/sessions",
        json={"specialization_code": "backend", "target_grade": target_grade},
        headers=_auth(token),
    )
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    item = start.json()["item"]

    seen: list[str] = []
    for _ in range(20):
        seen.append(item["id"])
        correct_index = answers[item["id"]]
        wrong_index = next(i for i in range(len(item["options"])) if i != correct_index)
        response = await client.post(
            f"/api/v1/testing/sessions/{session_id}/answers",
            json={
                "item_id": item["id"],
                "answer_index": correct_index if correct else wrong_index,
                "response_time_ms": 5000,
            },
            headers=_auth(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        if body["finished"]:
            body["result"]["seen_items"] = seen
            return body["result"]
        item = body["next_item"]
        assert item is not None
    raise AssertionError("тест не завершился за отведённое число шагов")


async def test_specializations_and_grades_available(client: AsyncClient) -> None:
    specs = await client.get("/api/v1/testing/specializations")
    assert specs.status_code == 200
    codes = {s["code"] for s in specs.json()}
    assert {"backend", "frontend", "devops"} <= codes

    grades = await client.get("/api/v1/testing/grades")
    assert grades.status_code == 200
    assert [g["code"] for g in grades.json()] == GRADE_ORDER


async def test_survey_returns_grade_options(client: AsyncClient) -> None:
    token = await _login(client, "survey@example.com")
    response = await client.post(
        "/api/v1/testing/survey",
        json={"industry": "it", "specialization_code": "backend", "answers": {"q1": "api"}},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["specialization_code"] == "backend"
    assert response.json()["grade_options"]


async def test_unknown_specialization_and_grade_are_rejected(client: AsyncClient) -> None:
    token = await _login(client, "bad-spec@example.com")
    assert (
        await client.post(
            "/api/v1/testing/survey",
            json={"industry": "it", "specialization_code": "no-such", "answers": {}},
            headers=_auth(token),
        )
    ).status_code == 404

    assert (
        await client.post(
            "/api/v1/testing/sessions",
            json={"specialization_code": "backend", "target_grade": "godlike"},
            headers=_auth(token),
        )
    ).status_code == 400


async def test_testing_requires_candidate_role(client: AsyncClient) -> None:
    token = await _login(client, "employer-testing@example.com", role="employer")
    response = await client.post(
        "/api/v1/testing/sessions",
        json={"specialization_code": "backend", "target_grade": "middle"},
        headers=_auth(token),
    )
    assert response.status_code == 403


async def test_all_correct_assigns_high_grade(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "strong@example.com")
    result = await _run_test(client, token, db_factory, correct=True)

    assert result["status"] == "completed"
    assert 10 <= result["items_answered"] <= 16
    assert result["result_grade"] in GRADE_ORDER
    assert GRADE_ORDER.index(result["result_grade"]) >= GRADE_ORDER.index("middle")
    assert result["category_id"] is not None
    assert result["grade_change_applied"] is True
    assert "первичное" in result["grade_change_reason"]
    assert result["current_grade"] == result["result_grade"]
    assert "все ответы верны" in " ".join(result["warnings"])
    assert len(result["seen_items"]) == len(set(result["seen_items"])), "задания не должны повторяться"


async def test_all_wrong_assigns_low_grade(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "weak@example.com")
    result = await _run_test(client, token, db_factory, correct=False)

    assert result["status"] == "completed"
    assert GRADE_ORDER.index(result["result_grade"]) <= GRADE_ORDER.index("junior")
    assert result["grade_change_applied"] is True


async def test_grade_is_not_lowered_automatically(client: AsyncClient, db_factory) -> None:
    """Неуспех на высоком уровне не отнимает уже подтверждённый грейд.

    Грейд подтверждается тестом: форма его не подставляет, поэтому сначала успешное
    прохождение, а затем неуспех на том же уровне.
    """
    token = await _login(client, "no-downgrade@example.com")
    confirmed = await _run_test(client, token, db_factory, correct=True, target_grade="senior")
    grade = confirmed["current_grade"]
    assert grade in GRADE_ORDER, "успешный тест подтверждает грейд"

    result = await _run_test(client, token, db_factory, correct=False, target_grade=grade)

    assert result["result_grade"] != grade  # тест провален
    assert result["grade_change_applied"] is False  # но грейд не понижен
    assert result["current_grade"] == grade
    assert "понижение" in result["grade_change_reason"].lower()


async def test_grade_change_cooldown_blocks_second_change(client: AsyncClient, db_factory) -> None:
    """Смена грейда ограничена по времени."""
    token = await _login(client, "cooldown@example.com")
    first = await _run_test(client, token, db_factory, correct=False)
    assert first["grade_change_applied"] is True  # первичное присвоение

    second = await _run_test(client, token, db_factory, correct=True)
    assert second["grade_change_applied"] is False
    assert "ограничена по времени" in second["grade_change_reason"]
    assert second["current_grade"] == first["current_grade"]


async def test_category_endpoint_reports_status_and_history(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "category@example.com")
    await _run_test(client, token, db_factory, correct=True)

    response = await client.get("/api/v1/testing/me/category", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["grade"] in GRADE_ORDER
    assert body["specialization"] == "backend"
    assert len(body["grade_history"]) == 1
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["status"] == "completed"
    assert body["grade_change_cooldown_days"] > 0
    assert body["grade_change_allowed"] is False  # сразу после смены — запрещено


async def test_exposure_counter_grows(client: AsyncClient, db_factory) -> None:
    """Контроль показов: предъявленные задания учитываются."""
    token = await _login(client, "exposure@example.com")
    result = await _run_test(client, token, db_factory, correct=True)

    async with db_factory() as session:
        used = (await session.execute(select(Item).where(Item.id.in_(result["seen_items"])))).scalars().all()
        assert all(item.exposure_count >= 1 for item in used)


# --- Незавершённый тест: возврат вместо потери прогресса ---------------------


async def _start(client, token, *, grade: str = "middle") -> dict:
    response = await client.post(
        "/api/v1/testing/sessions",
        json={"specialization_code": "backend", "target_grade": grade},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_unfinished_test_is_resumed_instead_of_restarted(client: AsyncClient, db_factory) -> None:
    """Повторный вход в тест продолжает его, а не создаёт вторую сессию."""
    token = await _login(client, "resume@example.com")
    answers = await _answer_key(db_factory)
    started = await _start(client, token)
    session_id, item = started["session_id"], started["item"]

    for _ in range(2):
        response = await client.post(
            f"/api/v1/testing/sessions/{session_id}/answers",
            json={"item_id": item["id"], "answer_index": answers[item["id"]], "response_time_ms": 5000},
            headers=_auth(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        if body["finished"]:
            break
        item = body["next_item"]

    again = await _start(client, token)
    assert again["session_id"] == session_id, "должна вернуться та же сессия"
    assert again["item"]["id"] == item["id"], "должно вернуться то же следующее задание"


async def test_category_reports_active_session_for_resume(client: AsyncClient, db_factory) -> None:
    """Кабинет видит, что тест не завершён, и с какого задания продолжить."""
    token = await _login(client, "active-session@example.com")
    started = await _start(client, token)

    response = await client.get("/api/v1/testing/me/category", headers=_auth(token))
    assert response.status_code == 200
    active = response.json()["active_session"]

    assert active is not None
    assert active["session_id"] == started["session_id"]
    assert active["items_answered"] == 0
    assert active["target_grade"] == "middle"
    assert active["next_item"]["id"] == started["item"]["id"]


async def test_finished_test_is_not_offered_for_resume(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "finished-session@example.com")
    await _run_test(client, token, db_factory, correct=True)

    body = (await client.get("/api/v1/testing/me/category", headers=_auth(token))).json()
    assert body["active_session"] is None


async def test_viewing_category_does_not_inflate_exposure(client: AsyncClient, db_factory) -> None:
    """Просмотр кабинета не должен считаться предъявлением задания."""
    token = await _login(client, "exposure-resume@example.com")
    started = await _start(client, token)
    item_id = started["item"]["id"]

    async with db_factory() as session:
        before = (await session.execute(select(Item).where(Item.id == item_id))).scalar_one().exposure_count

    for _ in range(3):
        await client.get("/api/v1/testing/me/category", headers=_auth(token))

    async with db_factory() as session:
        after = (await session.execute(select(Item).where(Item.id == item_id))).scalar_one().exposure_count

    assert after == before
