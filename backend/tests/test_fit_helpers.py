"""Тесты измерения сигналов кандидата: основа объяснимости подборки.

Здесь проверяется именно мера соответствия — то, что видит работодатель в
обосновании («совпадение стека: Python, PostgreSQL»), а не веса ранжирования.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.security import utcnow
from app.services.fit import (
    compute_fit,
    days_since,
    describe_fit,
    fsp_achievement_count,
    matched_stack,
    normalize_theta,
    signals_debug,
    stack_overlap,
)

ORDER = ("intern", "junior", "middle", "senior", "lead")


# --- нормировка способности --------------------------------------------------


def test_normalize_theta_is_centered_and_bounded() -> None:
    assert normalize_theta(None) is None
    assert normalize_theta(0.0) == 0.5
    high, low = normalize_theta(10.0), normalize_theta(-10.0)
    assert high is not None and low is not None
    assert high > 0.98
    assert low < 0.02


def test_normalize_theta_is_symmetric() -> None:
    positive, negative = normalize_theta(1.5), normalize_theta(-1.5)
    assert positive is not None and negative is not None
    assert positive == round(1 - negative, 4)


# --- пересечение стека -------------------------------------------------------


def test_stack_overlap_ignores_case_and_spaces() -> None:
    assert stack_overlap(["Python", " postgresql "], ["python", "PostgreSQL"]) == 1.0


def test_stack_overlap_is_partial_for_missing_technologies() -> None:
    assert stack_overlap(["Python", "Spark", "Kafka", "Docker"], ["Python", "Docker"]) == 0.5


def test_stack_overlap_without_requirements_is_zero() -> None:
    """Пустое требование — это отсутствие данных, а не полное совпадение."""
    assert stack_overlap([], ["Python"]) == 0.0
    assert stack_overlap(["  "], ["Python"]) == 0.0


def test_matched_stack_keeps_customer_wording() -> None:
    """В объяснении показываем термин из потребности, а не из профиля."""
    assert matched_stack(["Python", "PostgreSQL"], ["python", "Docker"]) == ["Python"]


# --- соответствие потребности ------------------------------------------------


def _fit(**overrides):
    payload = {
        "required_stack": ["Python", "PostgreSQL"],
        "candidate_stack": ["Python", "PostgreSQL"],
        "required_specialization": "backend",
        "candidate_specialization": "backend",
        "required_grade": "middle",
        "candidate_grade": "middle",
        "grade_order": ORDER,
    }
    payload.update(overrides)
    return compute_fit(**payload)


def test_fit_without_any_criteria_is_unknown_not_zero() -> None:
    """Отсутствующие данные не додумываются: возвращается None, а не 0."""
    assert (
        compute_fit(
            required_stack=[],
            candidate_stack=["Python"],
            required_specialization=None,
            candidate_specialization="backend",
            required_grade=None,
            candidate_grade="middle",
            grade_order=ORDER,
        )
        is None
    )


def _known(value: float | None) -> float:
    """Соответствие потребности должно быть числом — проверяем это явно."""
    assert value is not None
    return value


def test_fit_is_full_for_exact_match() -> None:
    assert _fit() == 1.0


def test_fit_drops_when_stack_is_only_partially_matched() -> None:
    assert _known(_fit(candidate_stack=["Python"])) < _known(_fit())


def test_fit_penalizes_specialization_mismatch() -> None:
    assert _known(_fit(candidate_specialization="frontend")) < _known(_fit())


def test_fit_penalizes_grade_distance() -> None:
    assert _known(_fit(candidate_grade="junior")) < _known(_fit())


def test_unknown_grade_does_not_break_matching() -> None:
    """Грейд вне шкалы не должен ронять подбор — сигнал просто теряет вес."""
    value = _fit(candidate_grade="godlike")
    assert value is not None
    assert 0.0 <= value <= 1.0


# --- свежесть и достижения ---------------------------------------------------


def test_days_since_handles_missing_and_future_values() -> None:
    assert days_since(None) is None
    assert days_since(utcnow() - timedelta(days=10)) == 10
    # Будущее не превращается в отрицательный возраст
    assert days_since(utcnow() + timedelta(days=5)) == 0


def test_fsp_achievement_count_counts_items() -> None:
    assert fsp_achievement_count([]) == 0
    assert fsp_achievement_count([{"title": "призёр"}, {"title": "финалист"}]) == 2


# --- объяснение для интерфейса ----------------------------------------------


def test_describe_fit_without_data_explains_why() -> None:
    assert "без стека" in describe_fit(None, [], [])


def test_describe_fit_lists_matched_technologies() -> None:
    text = describe_fit(0.8, ["Python", "Docker"], ["Python", "Docker"])
    assert "Python, Docker" in text


def test_describe_fit_without_overlap_says_so() -> None:
    assert "нет совпадений" in describe_fit(0.2, ["Python"], [])


def test_signals_debug_returns_independent_copy() -> None:
    payload = {"a": 1}
    copy = signals_debug(payload)
    copy["a"] = 2
    assert payload == {"a": 1}


@pytest.mark.parametrize("theta", [-3.0, -1.0, 0.0, 1.0, 3.0])
def test_normalize_theta_stays_within_unit_interval(theta: float) -> None:
    value = normalize_theta(theta)
    assert value is not None and 0.0 <= value <= 1.0
