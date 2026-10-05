"""Тесты адаптивной модели и правил грейдирования."""

from __future__ import annotations

import pytest

from app.services.testing import (
    GRADE_ORDER,
    Item,
    Response,
    can_change_grade,
    estimate_ability,
    grade_for_theta,
    next_grade_options,
    probability_correct,
    select_next_item,
)

ITEMS = {
    "easy": Item("easy", difficulty=-1.5),
    "mid": Item("mid", difficulty=0.0),
    "hard": Item("hard", difficulty=1.5),
}


def test_probability_correct_is_monotonic() -> None:
    low = probability_correct(-2.0, 0.0)
    mid = probability_correct(0.0, 0.0)
    high = probability_correct(2.0, 0.0)
    assert low < mid < high
    assert pytest.approx(mid, abs=1e-9) == 0.5


def test_estimate_ability_mixed_responses() -> None:
    responses = [
        Response("easy", correct=True),
        Response("mid", correct=True),
        Response("hard", correct=False),
    ]
    estimate = estimate_ability(responses, ITEMS)
    assert -6.0 <= estimate.theta <= 6.0
    assert estimate.standard_error > 0
    assert estimate.converged


def test_all_correct_is_flagged_not_invented() -> None:
    responses = [Response("easy", True), Response("mid", True), Response("hard", True)]
    estimate = estimate_ability(responses, ITEMS)
    assert estimate.warnings
    assert "верхняя граница" in " ".join(estimate.warnings)


def test_all_wrong_is_flagged() -> None:
    responses = [Response("easy", False), Response("mid", False), Response("hard", False)]
    estimate = estimate_ability(responses, ITEMS)
    assert estimate.warnings
    assert estimate.theta < 0


def test_empty_responses_returns_neutral() -> None:
    estimate = estimate_ability([], ITEMS)
    assert estimate.theta == 0.0
    assert estimate.warnings


def _selected_id(items, theta: float, used=()) -> str:
    item = select_next_item(list(items), theta=theta, used_item_ids=list(used))
    assert item is not None, "ожидалось выбранное задание"
    return item.id


def test_select_next_item_targets_current_ability() -> None:
    assert _selected_id(ITEMS.values(), theta=0.1) == "mid"
    assert _selected_id(ITEMS.values(), theta=1.4) == "hard"
    assert _selected_id(ITEMS.values(), theta=-1.4) == "easy"


def test_select_next_item_respects_exposure_and_used() -> None:
    exhausted = [Item("only", difficulty=0.0, max_exposure=5, exposure_count=5)]
    assert select_next_item(exhausted, theta=0.0) is None
    assert _selected_id(ITEMS.values(), theta=0.0, used=["mid"]) in {"easy", "hard"}


def test_grade_mapping() -> None:
    assert grade_for_theta(-3.5) == "intern"
    assert grade_for_theta(-0.8) == "junior"
    assert grade_for_theta(0.5) == "middle"
    assert grade_for_theta(2.5) == "lead"


def test_next_grade_options_include_lower_and_higher() -> None:
    options = next_grade_options("middle")
    assert "middle" in options and "junior_plus" in options and "senior" in options
    assert next_grade_options("lead") == ["lead", "senior"]
    assert next_grade_options(GRADE_ORDER[0]) == ["intern", "junior"]


def test_grade_change_cooldown() -> None:
    assert can_change_grade(None, 90) == (True, None)          # первичное присвоение
    assert can_change_grade(120, 90) == (True, None)           # срок прошёл
    allowed, remaining = can_change_grade(30, 90)
    assert allowed is False and remaining == 60                # смена ограничена по времени
