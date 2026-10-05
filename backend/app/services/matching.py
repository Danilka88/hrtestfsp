"""Ранжирование кандидатов и объяснимость выдачи.

Требование объяснимости: критерии и их веса **фиксируются до просмотра пула**
кандидатов. Поэтому веса объявлены константами модуля и не передаются
параметрами в рантайме — подборка всегда рассчитывается по одной рубрике.

Отсутствующие данные не додумываются: компонент даёт вклад 0 и попадает в
список `missing` с явной формулировкой «нет данных».
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

RUBRIC_VERSION = "rubric-1"

# Единственный источник весов. Сумма должна равняться 1.0.
WEIGHTS: Dict[str, float] = {
    "test_strength": 0.45,
    "fsp_achievements": 0.20,
    "freshness": 0.10,
    "semantic_fit": 0.25,
}

if abs(sum(WEIGHTS.values()) - 1.0) > 1e-9:  # pragma: no cover — защита контракта
    raise AssertionError("Сумма весов рубрики должна равняться 1.0")

FRESHNESS_FULL_DAYS = 30
FRESHNESS_ZERO_DAYS = 180
FSP_SATURATION = 2.0


@dataclass(frozen=True)
class CandidateSignals:
    """Сигналы кандидата, доступные на момент ранжирования."""

    candidate_id: str
    test_strength: Optional[float] = None       # 0..1, нормализованная оценка теста
    fsp_achievements: Optional[int] = None      # число подтверждённых достижений
    days_since_last_task: Optional[int] = None  # свежесть (регулярные задания)
    semantic_fit: Optional[float] = None        # 0..1, соответствие потребности
    # Соответствие запрошенной категории (специализация × грейд). Выдача
    # формируется на основании категорий, поэтому кандидаты запрошенной
    # категории идут выше — это первый ключ сортировки, а не слагаемое балла.
    in_requested_category: Optional[bool] = None


@dataclass
class Reason:
    """Объяснение вклада компонента — основа evidence-trail."""

    code: str
    text: str
    value: float
    contribution: float


@dataclass
class ScoredCandidate:
    candidate_id: str
    score: float
    reasons: List[Reason] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _fsp_component(count: int) -> float:
    """Насыщающийся вклад достижений: 0 → 0.0, 1 → 0.39, 2 → 0.63, 3 → 0.78."""
    if count <= 0:
        return 0.0
    return 1.0 - math.exp(-count / FSP_SATURATION)


def _freshness_component(days: Optional[int]) -> Optional[float]:
    if days is None:
        return None
    if days <= FRESHNESS_FULL_DAYS:
        return 1.0
    if days >= FRESHNESS_ZERO_DAYS:
        return 0.0
    span = FRESHNESS_ZERO_DAYS - FRESHNESS_FULL_DAYS
    return _clamp01((FRESHNESS_ZERO_DAYS - days) / span)


def _grade_words(value: float) -> str:
    if value >= 0.8:
        return "высокая"
    if value >= 0.5:
        return "средняя"
    return "низкая"


def score_candidate(signals: CandidateSignals) -> ScoredCandidate:
    """Оценка кандидата с полным evidence-trail."""
    reasons: List[Reason] = []
    missing: List[str] = []
    total = 0.0

    # 1. Сила подтверждённого профиля (результат теста)
    if signals.test_strength is None:
        missing.append("нет результата теста")
    else:
        value = _clamp01(signals.test_strength)
        contribution = WEIGHTS["test_strength"] * value
        total += contribution
        reasons.append(
            Reason(
                code="test_strength",
                text=f"Подтверждённый профиль: {_grade_words(value)} сила "
                     f"({value:.2f} по нормализованной шкале теста)",
                value=value,
                contribution=round(contribution, 4),
            )
        )

    # 2. Подтверждённые достижения
    if signals.fsp_achievements is None:
        missing.append("нет данных о достижениях (в том числе при отсутствии истории)")
    else:
        count = max(0, signals.fsp_achievements)
        value = _fsp_component(count)
        contribution = WEIGHTS["fsp_achievements"] * value
        total += contribution
        if count == 0:
            reasons.append(
                Reason(
                    code="fsp_achievements",
                    text="Подтверждённых достижений нет",
                    value=0.0,
                    contribution=0.0,
                )
            )
        else:
            reasons.append(
                Reason(
                    code="fsp_achievements",
                    text=f"Подтверждено достижений: {count}",
                    value=round(value, 4),
                    contribution=round(contribution, 4),
                )
            )

    # 3. Свежесть профиля
    fresh = _freshness_component(signals.days_since_last_task)
    if fresh is None:
        missing.append("нет отметок активности в регулярных заданиях")
    else:
        contribution = WEIGHTS["freshness"] * fresh
        total += contribution
        days = signals.days_since_last_task
        reasons.append(
            Reason(
                code="freshness",
                text=f"Профиль актуален: последняя активность {days} дн. назад",
                value=round(fresh, 4),
                contribution=round(contribution, 4),
            )
        )

    # 4. Семантическое соответствие потребности
    if signals.semantic_fit is None:
        missing.append("нет оценки соответствия потребности")
    else:
        value = _clamp01(signals.semantic_fit)
        contribution = WEIGHTS["semantic_fit"] * value
        total += contribution
        reasons.append(
            Reason(
                code="semantic_fit",
                text=f"Соответствие описанной потребности: {value:.0%}",
                value=round(value, 4),
                contribution=round(contribution, 4),
            )
        )

    return ScoredCandidate(
        candidate_id=signals.candidate_id,
        score=round(total, 4),
        reasons=reasons,
        missing=missing,
    )


def rank_candidates(signals: Sequence[CandidateSignals]) -> List[ScoredCandidate]:
    """Ранжирование подборки.

    Порядок: сначала кандидаты запрошенной категории (специализация × грейд),
    затем — остальные; внутри каждой группы по баллу рубрики. Такой порядок
    прямо следует правилу «выдача формируется на основании категорий, внутри
    категории — по силе подтверждённого профиля».

    Сортировка детерминирована: при равенстве баллов порядок задаёт candidate_id.
    """
    scored = [score_candidate(s) for s in signals]
    category_flag = {
        s.candidate_id: bool(s.in_requested_category) for s in signals
    }

    scored.sort(key=lambda c: (not category_flag[c.candidate_id], -c.score, c.candidate_id))

    for position, candidate in enumerate(scored, start=1):
        candidate.reasons.insert(
            0,
            Reason(
                code="rank",
                text=f"Позиция в подборке: {position}",
                value=float(position),
                contribution=0.0,
            ),
        )
        if category_flag.get(candidate.candidate_id):
            candidate.reasons.insert(
                1,
                Reason(
                    code="category_match",
                    text="Кандидат относится к запрошенной категории (специализация × грейд)",
                    value=1.0,
                    contribution=0.0,
                ),
            )
    return scored
