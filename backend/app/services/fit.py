"""Вычисление сигналов кандидата для ранжирования подборки.

Сигналы отделены от рубрики: здесь — только измерение (что мы знаем о кандидате),
веса и правила ранжирования живут в `app.services.matching`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from app.core.security import utcnow

# Нормализация оценки способности (θ ∈ ℝ) в шкалу 0..1
ABILITY_SCALE = 2.5


def normalize_theta(theta: float | None) -> float | None:
    """θ → 0..1 логистическим преобразованием."""
    if theta is None:
        return None
    return round(1.0 / (1.0 + math.exp(-theta / ABILITY_SCALE)), 4)


def stack_overlap(required: Sequence[str], actual: Sequence[str]) -> float:
    """Доля требуемых технологий, найденных у кандидата (0..1)."""
    required_set = {s.strip().lower() for s in required if s and s.strip()}
    if not required_set:
        return 0.0
    actual_set = {s.strip().lower() for s in actual if s and s.strip()}
    return round(len(required_set & actual_set) / len(required_set), 4)


def compute_fit(
    *,
    required_stack: Sequence[str],
    candidate_stack: Sequence[str],
    required_specialization: str | None,
    candidate_specialization: str | None,
    required_grade: str | None,
    candidate_grade: str | None,
    grade_order: Sequence[str],
) -> float | None:
    """Соответствие потребности работодателя (0..1).

    Простая, полностью объяснимая мера: пересечение стека и совпадение
    специализации/грейда. Семантические эмбеддинги подключаются за тем же
    интерфейсом позже; текущая мера фиксирует явные признаки, а не догадки.
    """
    has_any = bool(required_stack) or bool(required_specialization) or bool(required_grade)
    if not has_any:
        return None

    parts: list[float] = []
    weights: list[float] = []

    if required_stack:
        parts.append(stack_overlap(required_stack, candidate_stack))
        weights.append(0.6)

    if required_specialization:
        parts.append(1.0 if candidate_specialization == required_specialization else 0.0)
        weights.append(0.25)

    if required_grade and candidate_grade:
        try:
            distance = abs(list(grade_order).index(candidate_grade) - list(grade_order).index(required_grade))
        except ValueError:
            distance = len(grade_order)
        parts.append(max(0.0, 1.0 - distance / 3.0))
        weights.append(0.15)

    if not parts:
        return None
    total_weight = sum(weights)
    return round(sum(p * w for p, w in zip(parts, weights, strict=True)) / total_weight, 4)


def days_since(moment: datetime | None, now: datetime | None = None) -> int | None:
    if moment is None:
        return None
    reference = now or utcnow()
    return max(0, (reference - moment).days)


def fsp_achievement_count(achievements: Iterable[Any]) -> int:
    return len(list(achievements))


def describe_fit(fit: float | None, required_stack: Sequence[str], matched_stack: Sequence[str]) -> str:
    """Человекочитаемое объяснение соответствия требованиям."""
    if fit is None:
        return "Потребность описана без стека и специализации"
    matched = ", ".join(matched_stack) if matched_stack else "нет совпадений"
    return f"Совпадение стека по потребности: {matched}"


def matched_stack(required: Sequence[str], actual: Sequence[str]) -> list[str]:
    required_set = {s.strip().lower(): s for s in required if s and s.strip()}
    actual_lower = {s.strip().lower() for s in actual if s and s.strip()}
    return [original for key, original in required_set.items() if key in actual_lower]


def signals_debug(payload: dict[str, Any]) -> dict[str, Any]:
    """Служебное представление сигналов (используется в тестах и отладке)."""
    return dict(payload)
