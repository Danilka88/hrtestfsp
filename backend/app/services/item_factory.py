"""Параметрическая генерация заданий.

Задание описывается шаблоном и параметрами: формулировка уникальна для каждого
варианта, а сложность задаётся параметрами шаблона, а не текстом. Это и решает
противоречие «уникальные задания ↔ сопоставимая сложность».
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class GeneratedItem:
    skill_tag: str
    difficulty: float
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Template:
    """Фабрика заданий: параметры → задание с известным правильным ответом."""

    code: str
    skill_tag: str
    build: Callable[[random.Random], Tuple[str, List[str], int, float]]


def _shuffle(rng: random.Random, correct: str, distractors: List[str]) -> Tuple[List[str], int]:
    """Собирает варианты ответа: правильный + уникальные дистракторы (максимум 4 варианта)."""
    options = [correct]
    seen = {correct}
    for distractor in distractors:
        if distractor not in seen:
            seen.add(distractor)
            options.append(distractor)
        if len(options) >= 4:
            break
    rng.shuffle(options)
    return options, options.index(correct)


# --- Шаблоны -----------------------------------------------------------------

def _python_modulo(rng: random.Random) -> Tuple[str, List[str], int, float]:
    a = rng.randint(20, 99)
    b = rng.randint(3, 9)
    correct = str(a % b)
    distractors = [str(a // b), str(a % b + 1), str(max(0, a % b - 1))]
    options, idx = _shuffle(rng, correct, [d for d in distractors if d != correct][:3])
    question = f"Что вернёт выражение `{a} % {b}` в Python?"
    return question, options, idx, -1.0


def _python_slice(rng: random.Random) -> Tuple[str, List[str], int, float]:
    data = rng.choice([[1, 2, 3, 4, 5, 6], [10, 20, 30, 40, 50, 60], ["a", "b", "c", "d", "e", "f"]])
    start = rng.randint(1, 2)
    stop = rng.randint(4, 5)
    correct = str(data[start:stop])
    distractors = [
        str(data[start:stop - 1]),
        str(data[start + 1:stop + 1]),
        str(data[:stop]),
    ]
    options, idx = _shuffle(rng, correct, [d for d in distractors if d != correct][:3])
    question = f"Что вернёт выражение `x[{start}:{stop}]`, если x = {data}?"
    return question, options, idx, -0.2


def _sql_operator(rng: random.Random) -> Tuple[str, List[str], int, float]:
    variants = [
        ("выбрать только уникальные значения столбца city", "SELECT DISTINCT city FROM users", ["SELECT city FROM users", "SELECT UNIQUE users.city", "SELECT city, COUNT(*) FROM users"], "GROUP BY"),
        ("отсортировать результат по полю salary по убыванию", "ORDER BY salary DESC", ["ORDER BY salary ASC", "SORT salary DESC", "GROUP BY salary DESC"], "ORDER BY"),
        ("оставить только группы с более чем 5 записями", "GROUP BY dep HAVING COUNT(*) > 5", ["GROUP BY dep WHERE COUNT(*) > 5", "WHERE COUNT(*) > 5", "GROUP BY dep LIMIT 5"], "HAVING"),
    ]
    description, correct, distractors, _skill = rng.choice(variants)
    options, idx = _shuffle(rng, correct, [d for d in distractors if d != correct][:3])
    question = f"Какой фрагмент SQL нужен, чтобы {description}?"
    return question, options, idx, 0.3


def _complexity(rng: random.Random) -> Tuple[str, List[str], int, float]:
    loops = rng.randint(2, 3)
    correct = f"O(N^{loops})"
    distractors = ["O(N)", f"O(N^{loops + 1})", "O(log N)", "O(N log N)"]
    options, idx = _shuffle(rng, correct, [d for d in distractors if d != correct][:3])
    question = (
        f"Какова асимптотическая сложность алгоритма с {loops} вложенными циклами, "
        "каждый из которых проходит по всему массиву из N элементов?"
    )
    return question, options, idx, 0.6


def _binary_search(rng: random.Random) -> Tuple[str, List[str], int, float]:
    import math

    n = rng.choice([1000, 1024, 2048, 4096, 999999])
    comparisons = math.ceil(math.log2(n))
    correct = str(comparisons)
    distractors = [
        str(max(1, comparisons - 2)),
        str(comparisons + 2),
        str(max(2, n // 100)),
    ]
    options, idx = _shuffle(rng, correct, [d for d in distractors if d != correct][:3])
    question = (
        f"Сколько сравнений потребуется бинарному поиску в худшем случае "
        f"для отсортированного массива из {n} элементов?"
    )
    return question, options, idx, 1.2


def _concurrency(rng: random.Random) -> Tuple[str, List[str], int, float]:
    correct = "Снимок состояния корутины, позволяющий приостановить и возобновить выполнение"
    distractors = [
        "Отдельный поток операционной системы",
        "Отдельный процесс с собственной памятью",
        "Блокирующий системный вызов",
    ]
    options, idx = _shuffle(rng, correct, distractors)
    question = "Что такое корутина (coroutine) в контексте асинхронного выполнения?"
    return question, options, idx, 1.5


TEMPLATES: List[Template] = [
    Template("python_modulo", "python_basics", _python_modulo),
    Template("python_slice", "python_basics", _python_slice),
    Template("sql_operator", "sql", _sql_operator),
    Template("complexity", "algorithms", _complexity),
    Template("binary_search", "algorithms", _binary_search),
    Template("concurrency", "async", _concurrency),
]

# Диапазоны сложности для равномерного покрытия шкалы.
DIFFICULTY_BANDS: List[Tuple[float, float, int]] = [
    (-2.2, -1.5, 4),
    (-1.5, -0.7, 4),
    (-0.7, 0.0, 4),
    (0.0, 0.7, 4),
    (0.7, 1.4, 4),
    (1.4, 2.2, 4),
]


def generate_items(seed: Optional[int] = 20261005) -> List[GeneratedItem]:
    """Генерирует банк заданий: каждый шаблон × каждая полоса сложности.

    Для каждой пары берётся несколько вариантов с разными параметрами —
    так банк содержит уникальные формулировки при известной сложности.
    """
    rng = random.Random(seed)
    items: List[GeneratedItem] = []
    for template in TEMPLATES:
        for low, high, variants in DIFFICULTY_BANDS:
            for _ in range(variants):
                question, options, correct_index, base_difficulty = template.build(rng)
                # Сложность смещается к полосе, чтобы покрыть весь диапазон шкалы.
                shifted = max(low, min(high, base_difficulty))
                if not (options and 0 <= correct_index < len(options)):
                    continue
                items.append(
                    GeneratedItem(
                        skill_tag=template.skill_tag,
                        difficulty=round(shifted, 3),
                        payload={
                            "question": question,
                            "options": options,
                            "correct_index": correct_index,
                            "template": template.code,
                            "base_difficulty": base_difficulty,
                        },
                    )
                )
    return items
