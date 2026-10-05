"""Процедура валидации решения.

Эталонной разметки в рамках хакатона нет, поэтому команда предлагает собственную
процедуру и приводит результаты. Скрипт полностью детерминирован (фиксированные
seed), не требует БД и внешних сервисов — результат воспроизводим.

Запуск: python scripts/validate_solution.py [--runs N]

Что измеряется:
1. Стабильность грейда при повторном прохождении теста (test–retest).
2. Точность присвоения грейда относительно истинной способности.
3. Дискриминативность: разделение слабых и сильных кандидатов.
4. Контроль показов заданий (устойчивость к «расхождению» банка).
5. Релевантность подборки (Precision@5) на синтетических парах
   «потребность — кандидат» с независимой разметкой.
6. Детерминированность ранжирования.
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.fit import compute_fit, stack_overlap  # noqa: E402
from app.services.item_factory import generate_items  # noqa: E402
from app.services.matching import CandidateSignals, rank_candidates  # noqa: E402
from app.services.testing import (  # noqa: E402
    GRADE_ORDER,
    Response,
    estimate_ability,
    grade_for_theta,
    probability_correct,
    select_next_item,
)
from app.services.testing import (
    Item as CoreItem,
)

MIN_ITEMS = 10
MAX_ITEMS = 16
TARGET_SE = 0.38

STACKS = {
    "backend": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Redis", "Kafka"],
    "frontend": ["JavaScript", "TypeScript", "React", "Vue", "Node.js", "Docker"],
    "devops": ["Linux", "Docker", "Kubernetes", "Git", "Redis"],
    "qa": ["SQL", "Git", "Linux", "Python"],
}


@dataclass
class Bank:
    """Банк заданий в представлении ядра (без БД)."""

    items: list[CoreItem]

    def core(self) -> list[CoreItem]:
        return list(self.items)


def build_bank(seed: int = 20261005) -> Bank:
    generated = generate_items(seed=seed)
    items = [
        CoreItem(id=f"i{index}", difficulty=item.difficulty, discrimination=1.0)
        for index, item in enumerate(generated)
    ]
    return Bank(items=items)


def run_session(
    rng: random.Random,
    bank: Bank,
    theta_true: float,
    *,
    exposure_counter: dict[str, int] | None = None,
) -> tuple[float, float, int, list[str], dict[str, int]]:
    """Проходит один адаптивный тест. Возвращает θ, ошибку, число заданий, порядок, показы.

    Счётчик показов передаётся в выбор задания так же, как это делает сервис по
    данным БД: задания с исчерпанным лимитом не предлагаются, а слабо
    использованные получают приоритет. Без этого симуляция завышала бы нагрузку
    на популярные задания.
    """
    counters: dict[str, int] = exposure_counter if exposure_counter is not None else {}
    used: list[str] = []
    responses: list[Response] = []
    session_exposures: dict[str, int] = {}

    def pool() -> list[CoreItem]:
        return [replace(item, exposure_count=counters.get(item.id, 0)) for item in bank.items]

    next_item = select_next_item(pool(), theta=0.0)
    while next_item is not None:
        used.append(next_item.id)
        counters[next_item.id] = counters.get(next_item.id, 0) + 1
        session_exposures[next_item.id] = session_exposures.get(next_item.id, 0) + 1

        p_correct = probability_correct(theta_true, next_item.difficulty, next_item.discrimination)
        responses.append(Response(item_id=next_item.id, correct=rng.random() < p_correct))

        estimate = estimate_ability(responses, {item.id: item for item in bank.items})
        if len(responses) >= MAX_ITEMS or (
            len(responses) >= MIN_ITEMS and estimate.standard_error <= TARGET_SE
        ):
            return estimate.theta, estimate.standard_error, len(responses), used, session_exposures

        following = select_next_item(pool(), estimate.theta, used_item_ids=used)
        if following is None:
            return estimate.theta, estimate.standard_error, len(responses), used, session_exposures
        next_item = following

    estimate = estimate_ability(responses, {item.id: item for item in bank.items})
    return estimate.theta, estimate.standard_error, len(responses), used, session_exposures


# --- 1–2. Стабильность и точность грейда -------------------------------------


def measure_test_retest(bank: Bank, runs: int, seed: int = 11) -> dict[str, float]:
    rng = random.Random(seed)
    truth = [-1.8, -1.0, -0.3, 0.3, 0.9, 1.8, 2.4]
    matches = 0
    total = 0
    spreads: list[float] = []

    for theta_true in truth:
        grades = []
        for _ in range(max(1, runs // len(truth))):
            theta_hat, _, _, _, _ = run_session(rng, bank, theta_true)
            grades.append(grade_for_theta(theta_hat))
        total += len(grades)
        # стабильность = доля повторных прохождений, давших самую частую оценку
        most_common = statistics.mode(grades)
        matches += sum(1 for g in grades if g == most_common)
        spreads.append(len(set(grades)))

    return {
        "retest_agreement": matches / total,
        "mean_distinct_grades": statistics.mean(spreads),
        "sessions": total,
    }


def measure_grade_accuracy(bank: Bank, runs: int, seed: int = 23) -> dict[str, float]:
    """Точность: сравнение присвоенного грейда с грейдом истинной способности."""
    rng = random.Random(seed)
    correct = 0
    total = 0
    errors: list[int] = []

    for _ in range(runs):
        theta_true = rng.uniform(-2.2, 2.6)
        theta_hat, _, _, _, _ = run_session(rng, bank, theta_true)
        expected = grade_for_theta(theta_true)
        actual = grade_for_theta(theta_hat)
        total += 1
        correct += int(expected == actual)
        errors.append(abs(GRADE_ORDER.index(expected) - GRADE_ORDER.index(actual)))

    return {
        "exact_grade_accuracy": correct / total,
        "max_grade_error": max(errors),
        "mean_grade_error": statistics.mean(errors),
        "sessions": total,
    }


# --- 3. Дискриминативность ----------------------------------------------------


def measure_discrimination(bank: Bank, runs: int, seed: int = 37) -> dict[str, float]:
    rng = random.Random(seed)
    weak = [run_session(rng, bank, -1.5)[0] for _ in range(runs)]
    strong = [run_session(rng, bank, 1.5)[0] for _ in range(runs)]

    pooled = weak + strong
    var_all = statistics.pvariance(pooled) or 1e-9
    # разность средних в единицах общего разброса — грубая мера разделения
    separation = (statistics.mean(strong) - statistics.mean(weak)) / (var_all**0.5)

    overlaps = sum(1 for w in weak for s in strong if w >= s)
    return {
        "mean_theta_weak": statistics.mean(weak),
        "mean_theta_strong": statistics.mean(strong),
        "separation_effect_size": separation,
        "pairwise_inversions": overlaps / (len(weak) * len(strong)),
    }


# --- 4. Контроль показов ------------------------------------------------------


def measure_exposure(bank: Bank, runs: int, seed: int = 41) -> dict[str, float]:
    rng = random.Random(seed)
    exposure: dict[str, int] = {}
    for _ in range(runs):
        run_session(rng, bank, rng.uniform(-2.0, 2.4), exposure_counter=exposure)

    bank_size = len(bank.items)
    used = len(exposure)
    counts = list(exposure.values()) or [0]
    return {
        "bank_size": bank_size,
        "unique_items_used": used,
        "bank_coverage": used / bank_size,
        "max_item_exposure": max(counts),
        "mean_item_exposure": statistics.mean(counts),
        "sessions": runs,
    }


# --- 5. Релевантность подборки ------------------------------------------------


@dataclass
class SyntheticCandidate:
    reference: str
    specialization: str
    grade: str
    stack: list[str]
    theta: float
    fsp_achievements: int
    days_since_activity: int


@dataclass
class SyntheticNeed:
    reference: str
    specialization: str
    grade: str
    stack: list[str]


def build_dataset(
    rng: random.Random, size: int = 120
) -> tuple[list[SyntheticCandidate], list[SyntheticNeed]]:
    candidates: list[SyntheticCandidate] = []
    specializations = list(STACKS)
    for index in range(size):
        spec = rng.choice(specializations)
        grade = rng.choice(GRADE_ORDER[1:5])
        pool = STACKS[spec]
        stack = rng.sample(pool, rng.randint(2, len(pool)))
        candidates.append(
            SyntheticCandidate(
                reference=f"c{index:03d}",
                specialization=spec,
                grade=grade,
                stack=stack,
                theta=rng.uniform(-2.0, 2.4),
                fsp_achievements=rng.choice([0, 0, 1, 2, 3]),
                days_since_activity=rng.choice([0, 5, 20, 60, 120, 300]),
            )
        )

    needs: list[SyntheticNeed] = []
    for index in range(24):
        spec = rng.choice(specializations)
        needs.append(
            SyntheticNeed(
                reference=f"n{index:02d}",
                specialization=spec,
                grade=rng.choice(GRADE_ORDER[1:5]),
                stack=rng.sample(STACKS[spec], rng.randint(2, 3)),
            )
        )
    return candidates, needs


def ground_truth_relevant(candidate: SyntheticCandidate, need: SyntheticNeed) -> bool:
    """Независимая разметка: строгое совпадение специализации и грейда плюс
    покрытие стека не менее 60%. Не совпадает с формулой ранжирования."""
    if candidate.specialization != need.specialization:
        return False
    if candidate.grade != need.grade:
        return False
    return stack_overlap(need.stack, candidate.stack) >= 0.6


def measure_precision(
    candidates: Sequence[SyntheticCandidate], needs: Sequence[SyntheticNeed], k: int = 5
) -> dict[str, float]:
    precisions: list[float] = []
    recalls: list[float] = []

    for need in needs:
        signals = []
        for candidate in candidates:
            fit = compute_fit(
                required_stack=need.stack,
                candidate_stack=candidate.stack,
                required_specialization=need.specialization,
                candidate_specialization=candidate.specialization,
                required_grade=need.grade,
                candidate_grade=candidate.grade,
                grade_order=GRADE_ORDER,
            )
            signals.append(
                CandidateSignals(
                    candidate_id=candidate.reference,
                    test_strength=1.0 / (1.0 + pow(2.718281828, -candidate.theta / 2.5)),
                    fsp_achievements=candidate.fsp_achievements,
                    days_since_last_task=candidate.days_since_activity,
                    semantic_fit=fit,
                    # Выдача строится по категориям: совпадение специализации и грейда
                    in_requested_category=(
                        candidate.specialization == need.specialization and candidate.grade == need.grade
                    ),
                )
            )

        ranked = rank_candidates(signals)
        top = ranked[:k]

        relevant_total = sum(1 for c in candidates if ground_truth_relevant(c, need))
        relevant_in_top = 0
        for scored in top:
            candidate = next(c for c in candidates if c.reference == scored.candidate_id)
            if ground_truth_relevant(candidate, need):
                relevant_in_top += 1

        precisions.append(relevant_in_top / k)
        if relevant_total:
            recalls.append(relevant_in_top / relevant_total)

    return {
        f"precision_at_{k}": statistics.mean(precisions) if precisions else 0.0,
        f"recall_at_{k}": statistics.mean(recalls) if recalls else 0.0,
        "needs_evaluated": len(precisions),
    }


def measure_ranking_determinism(candidates: Sequence[SyntheticCandidate]) -> bool:
    """Повторный расчёт по тем же данным должен давать тот же порядок."""
    signals = [
        CandidateSignals(
            candidate_id=candidate.reference,
            test_strength=0.5,
            fsp_achievements=candidate.fsp_achievements,
            days_since_last_task=candidate.days_since_activity,
            semantic_fit=0.5,
        )
        for candidate in candidates
    ]
    first = [c.candidate_id for c in rank_candidates(signals)]
    second = [c.candidate_id for c in rank_candidates(list(reversed(signals)))]
    return first == second


def main() -> None:
    parser = argparse.ArgumentParser(description="Валидация решения")
    parser.add_argument("--runs", type=int, default=120, help="число сессий/примеров")
    args = parser.parse_args()

    bank = build_bank()
    print("=" * 72)
    print("ВАЛИДАЦИЯ РЕШЕНИЯ — платформа обратного подбора ИТ-специалистов")
    print("=" * 72)
    print(
        f"Банк заданий: {len(bank.items)} заданий, "
        f"сложность {min(i.difficulty for i in bank.items):.2f}…"
        f"{max(i.difficulty for i in bank.items):.2f}"
    )
    print(f"Число прогонов на метрику: {args.runs}")
    print()

    retest = measure_test_retest(bank, args.runs)
    print("1. Стабильность грейда при повторном прохождении (test–retest)")
    print(f"   согласованность: {retest['retest_agreement']:.1%}")
    print(
        f"   различных грейдов на одну истинную способность (в среднем): {retest['mean_distinct_grades']:.2f}"
    )
    print(f"   сессий: {int(retest['sessions'])}")
    print()

    accuracy = measure_grade_accuracy(bank, args.runs)
    print("2. Точность присвоения грейда относительно истинной способности")
    print(f"   точное совпадение грейда: {accuracy['exact_grade_accuracy']:.1%}")
    print(f"   средняя ошибка в шагах грейда: {accuracy['mean_grade_error']:.2f}")
    print(f"   максимальная ошибка: {accuracy['max_grade_error']}")
    print(f"   сессий: {int(accuracy['sessions'])}")
    print()

    discrimination = measure_discrimination(bank, args.runs)
    print("3. Дискриминативность (разделение слабых и сильных)")
    print(f"   средняя θ слабых:  {discrimination['mean_theta_weak']:.2f}")
    print(f"   средняя θ сильных: {discrimination['mean_theta_strong']:.2f}")
    print(f"   величина разделения (в единицах разброса): {discrimination['separation_effect_size']:.2f}")
    print(f"   доля инверсий «слабый ≥ сильный»: {discrimination['pairwise_inversions']:.1%}")
    print()

    exposure = measure_exposure(bank, args.runs)
    print("4. Контроль показов заданий")
    print(
        f"   использовано уникальных заданий: {int(exposure['unique_items_used'])} "
        f"из {int(exposure['bank_size'])} ({exposure['bank_coverage']:.0%})"
    )
    print(f"   максимальное число показов одного задания: {int(exposure['max_item_exposure'])}")
    print(f"   среднее число показов на задание: {exposure['mean_item_exposure']:.1f}")
    print(f"   сессий: {int(exposure['sessions'])}")
    print()

    rng = random.Random(2026)
    candidates, needs = build_dataset(rng)
    precision = measure_precision(candidates, needs, k=5)
    print("5. Релевантность подборки (независимая разметка)")
    print(f"   кандидатов в наборе: {len(candidates)}, потребностей: {len(needs)}")
    print(f"   Precision@5: {precision['precision_at_5']:.2f}")
    print(f"   Recall@5:    {precision['recall_at_5']:.2f}")
    print()

    deterministic = measure_ranking_determinism(candidates)
    print("6. Детерминированность ранжирования")
    print(f"   повторный расчёт даёт тот же порядок: {'да' if deterministic else 'НЕТ'}")
    print()
    print("=" * 72)


if __name__ == "__main__":
    main()
