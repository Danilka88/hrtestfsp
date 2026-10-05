"""Механика тестирования: адаптивный подбор заданий и грейдирование.

Этап 0 — минимально жизнеспособное ядро (модель Раша, детерминированное,
без внешних зависимостей). Расширение до полной IRT и параметрической генерации
заданий — Этап 3. Модуль намеренно не зависит от БД, что делает его тестируемым.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

# Порог оценки способности (θ) для нижней границы грейда.
# Грейд определяется тестом, а не самооценкой кандидата.
GRADE_THRESHOLDS: dict[str, float] = {
    "intern": -3.0,
    "junior": -1.0,
    "junior_plus": -0.5,
    "middle": 0.3,
    "senior": 1.0,
    "lead": 1.8,
}

# Порядок грейдов по возрастанию — используется для правил смены грейда.
GRADE_ORDER: list[str] = ["intern", "junior", "junior_plus", "middle", "senior", "lead"]


@dataclass(frozen=True)
class Item:
    """Задание в банке.

    Сложность задаётся параметром (b), а не текстом, — это и позволяет
    совмещать уникальность формулировок с сопоставимой сложностью.
    """

    id: str
    difficulty: float
    discrimination: float = 1.0
    max_exposure: int = 100
    exposure_count: int = 0

    @property
    def available(self) -> bool:
        return self.exposure_count < self.max_exposure


@dataclass(frozen=True)
class Response:
    item_id: str
    correct: bool
    response_time_ms: int | None = None


@dataclass
class AbilityEstimate:
    theta: float
    standard_error: float
    iterations: int
    converged: bool
    warnings: list[str] = field(default_factory=list)


def probability_correct(theta: float, difficulty: float, discrimination: float = 1.0) -> float:
    """P(верно) для логистической модели (при a=1 — модель Раша)."""
    z = discrimination * (theta - difficulty)
    if z > 40:
        return 1.0
    if z < -40:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def estimate_ability(
    responses: Sequence[Response],
    items: dict[str, Item],
    max_iterations: int = 60,
    tolerance: float = 1e-6,
) -> AbilityEstimate:
    """Оценка способности θ методом максимального правдоподобия (Ньютон–Рафсон).

    Крайние случаи (все ответы верны / все неверны) не дают конечной оценки —
    возвращается граничное значение с предупреждением, что отражается в UI
    как «диапазон не определён точно», без додумывания результата.
    """
    known = [(r, items[r.item_id]) for r in responses if r.item_id in items]
    warnings: list[str] = []

    if not known:
        return AbilityEstimate(0.0, 99.0, 0, False, ["нет данных для оценки"])

    theta = 0.0
    converged = False
    iterations = 0

    for _ in range(max_iterations):
        iterations += 1
        grad = 0.0
        info = 0.0
        for resp, item in known:
            p = probability_correct(theta, item.difficulty, item.discrimination)
            x = 1.0 if resp.correct else 0.0
            grad += item.discrimination * (x - p)
            info += (item.discrimination**2) * p * (1.0 - p)

        if info <= 1e-9:
            break
        step = grad / info
        theta += step
        if abs(step) < tolerance:
            converged = True
            break

    # Ограничение диапазона и явные предупреждения о крайних случаях
    if all(r.correct for r, _ in known):
        theta = max(item.difficulty for _, item in known) + 1.8
        warnings.append("все ответы верны: верхняя граница диапазона")
        converged = False
    elif not any(r.correct for r, _ in known):
        theta = min(item.difficulty for _, item in known) - 1.8
        warnings.append("все ответы неверны: нижняя граница диапазона")
        converged = False
    else:
        hardest = max(item.difficulty for _, item in known)
        easiest = min(item.difficulty for _, item in known)
        theta = max(-6.0, min(6.0, theta))
        if theta >= hardest + 0.5:
            warnings.append("оценка на верхней границе предъявленных заданий")
        if theta <= easiest - 0.5:
            warnings.append("оценка на нижней границе предъявленных заданий")

    # Стандартная ошибка оценки: 1 / sqrt(информация)
    total_info = 0.0
    for _, item in known:
        p = probability_correct(theta, item.difficulty, item.discrimination)
        total_info += (item.discrimination**2) * p * (1.0 - p)

    se = 99.0 if total_info <= 1e-9 else 1.0 / math.sqrt(total_info)

    return AbilityEstimate(
        theta=round(theta, 4),
        standard_error=round(se, 4),
        iterations=iterations,
        converged=converged,
        warnings=warnings,
    )


def select_next_item(
    items: Sequence[Item],
    theta: float,
    used_item_ids: Sequence[str] = (),
) -> Item | None:
    """Выбор следующего задания.

    Критерий: минимум |b − θ| (максимум информации при текущей оценке).
    Учитывается контроль показов (exposure) и запрет повторов.
    """
    used = set(used_item_ids)
    candidates = [i for i in items if i.available and i.id not in used]
    if not candidates:
        return None
    return min(candidates, key=lambda i: (abs(i.difficulty - theta), i.exposure_count, i.id))


def grade_for_theta(theta: float, thresholds: dict[str, float] | None = None) -> str:
    """Отображение оценки способности на шкалу грейдов."""
    limits = thresholds or GRADE_THRESHOLDS
    result = GRADE_ORDER[0]
    for code, minimum in sorted(limits.items(), key=lambda kv: kv[1]):
        if code in GRADE_ORDER and theta >= minimum:
            result = code
    return result


def next_grade_options(current_grade: str) -> list[str]:
    """Допустимые уровни тестирования относительно текущего грейда.

    Грейд не понижается принудительно: после неуспеха доступен уровень ниже,
    успешный кандидат может претендовать на уровень выше.
    """
    if current_grade not in GRADE_ORDER:
        return list(GRADE_ORDER)
    idx = GRADE_ORDER.index(current_grade)
    options = [GRADE_ORDER[idx]]
    if idx > 0:
        options.append(GRADE_ORDER[idx - 1])
    if idx < len(GRADE_ORDER) - 1:
        options.append(GRADE_ORDER[idx + 1])
    return options


def can_change_grade(
    last_change_days_ago: int | None,
    cooldown_days: int,
) -> tuple[bool, int | None]:
    """Проверка ограничения частоты смены грейда.

    Первичное присвоение грейда (`None`) сменой не считается.
    Возвращает (можно_ли, сколько_дней_осталось).
    """
    if last_change_days_ago is None:
        return True, None
    if last_change_days_ago >= cooldown_days:
        return True, None
    return False, cooldown_days - last_change_days_ago
