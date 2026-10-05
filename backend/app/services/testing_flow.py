"""Сценарий прохождения теста: адаптивная выдача, оценка, присвоение категории.

Ключевые правила:
* грейд определяется результатом теста, а не самооценкой кандидата;
* грейд не понижается принудительно — неуспех на высоком уровне не отнимает
  текущий грейд, результат остаётся только в истории;
* смена грейда ограничена по времени (интервал настраивается);
* контроль показов заданий (`exposure`) и подозрительно быстрое прохождение
  сложных заданий фиксируются как аномалии.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import utcnow
from app.models.candidate import DEFAULT_PRIVACY, CandidateProfile
from app.models.testing import (
    SESSION_COMPLETED,
    SESSION_IN_PROGRESS,
    Category,
    GradeChange,
    Item,
    ItemResponseRecord,
    Specialization,
    SurveyResponse,
    TestSession,
)
from app.services.testing import (
    GRADE_ORDER,
    AbilityEstimate,
    Response,
    can_change_grade,
    estimate_ability,
    grade_for_theta,
    next_grade_options,
    select_next_item,
)

logger = logging.getLogger(__name__)

MIN_ITEMS = 6
MAX_ITEMS = 12
TARGET_STANDARD_ERROR = 0.45
FAST_ANSWER_MS = 1500


class TestingError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class AnswerOutcome:
    correct: bool
    next_item: Optional[Dict[str, Any]]
    finished: bool
    result: Optional[Dict[str, Any]] = None


def public_item(item: Item) -> Dict[str, Any]:
    """Представление задания для кандидата: без правильного ответа и сложности."""
    payload = item.payload or {}
    return {
        "id": item.id,
        "skill_tag": item.skill_tag,
        "question": payload.get("question"),
        "options": payload.get("options", []),
    }


def _item_to_core(item: Item):
    from app.services.testing import Item as CoreItem

    return CoreItem(
        id=item.id,
        difficulty=item.difficulty,
        discrimination=item.discrimination,
        max_exposure=item.max_exposure,
        exposure_count=item.exposure_count,
    )


async def get_specialization(session: AsyncSession, code: str) -> Specialization:
    result = await session.execute(select(Specialization).where(Specialization.code == code))
    spec = result.scalar_one_or_none()
    if spec is None or not spec.is_active:
        raise TestingError(404, "Специализация не найдена")
    return spec


async def _load_items(session: AsyncSession, specialization_id: int) -> List[Item]:
    result = await session.execute(
        select(Item).where(Item.is_active.is_(True)).order_by(Item.difficulty)
    )
    items = list(result.scalars().all())
    # Сначала задания целевой специализации, затем — общие
    items.sort(key=lambda i: (i.specialization_id != specialization_id, i.difficulty))
    return items


async def _ensure_profile(session: AsyncSession, user_id: str) -> CandidateProfile:
    result = await session.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = CandidateProfile(
            user_id=user_id, contacts={}, stack=[], roles=[], soft_skills=[],
            privacy=dict(DEFAULT_PRIVACY),
        )
        session.add(profile)
        await session.flush()
    return profile


async def save_survey(
    session: AsyncSession, user_id: str, *, industry: str, specialization_code: str,
    answers: Dict[str, Any],
) -> tuple[SurveyResponse, List[str]]:
    """Опрос по отрасли и специализации + подсказка допустимых уровней теста."""
    spec = await get_specialization(session, specialization_code)
    record = SurveyResponse(
        user_id=user_id, industry=industry, specialization_id=spec.id, answers=answers or {}
    )
    session.add(record)

    profile = await _ensure_profile(session, user_id)
    if not profile.specialization:
        profile.specialization = spec.code

    await session.commit()
    await session.refresh(record)
    return record, next_grade_options(profile.grade or "junior")


async def start_session(
    session: AsyncSession, user_id: str, *, specialization_code: str, target_grade: str
) -> tuple[TestSession, Dict[str, Any]]:
    if target_grade not in GRADE_ORDER:
        raise TestingError(400, "Неизвестный грейд")
    spec = await get_specialization(session, specialization_code)

    items = await _load_items(session, spec.id)
    if not items:
        raise TestingError(503, "Банк заданий пуст")

    test_session = TestSession(
        user_id=user_id, specialization_id=spec.id, target_grade=target_grade,
        status=SESSION_IN_PROGRESS, warnings=[],
    )
    session.add(test_session)
    await session.flush()

    first = select_next_item([_item_to_core(i) for i in items], theta=0.0)
    if first is None:
        raise TestingError(503, "Нет доступных заданий")
    item = next(i for i in items if i.id == first.id)
    item.exposure_count += 1

    await session.commit()
    await session.refresh(test_session)
    return test_session, public_item(item)


async def submit_answer(
    session: AsyncSession, user_id: str, *, session_id: str, item_id: str,
    answer_index: int, response_time_ms: Optional[int] = None,
) -> AnswerOutcome:
    test_session = await session.get(TestSession, session_id)
    if test_session is None or test_session.user_id != user_id:
        raise TestingError(404, "Сессия тестирования не найдена")
    if test_session.status != SESSION_IN_PROGRESS:
        raise TestingError(409, "Сессия уже завершена")

    item = await session.get(Item, item_id)
    if item is None:
        raise TestingError(404, "Задание не найдено")

    payload = item.payload or {}
    correct_index = payload.get("correct_index")
    if not isinstance(correct_index, int):
        raise TestingError(500, "Некорректное задание в банке")
    correct = answer_index == correct_index

    if response_time_ms is not None and item.difficulty > 0.5 and response_time_ms < FAST_ANSWER_MS:
        note = f"подозрительно быстрое решение сложного задания ({item.difficulty:.2f})"
        if note not in (test_session.warnings or []):
            test_session.warnings = [*(test_session.warnings or []), note]

    session.add(
        ItemResponseRecord(
            session_id=test_session.id, item_id=item.id, correct=correct,
            response_time_ms=response_time_ms, answer={"index": answer_index},
        )
    )
    test_session.item_count += 1
    await session.flush()

    items = await _load_items(session, test_session.specialization_id)
    responses = await _load_responses(session, test_session.id)
    items_map = {i.id: _item_to_core(i) for i in items}

    estimate = estimate_ability(
        [Response(item_id=r.item_id, correct=r.correct, response_time_ms=r.response_time_ms)
         for r in responses],
        items_map,
    )
    test_session.theta = estimate.theta
    test_session.standard_error = estimate.standard_error

    enough_items = test_session.item_count >= MIN_ITEMS
    precise_enough = estimate.standard_error <= TARGET_STANDARD_ERROR
    limit_reached = test_session.item_count >= MAX_ITEMS

    if limit_reached or (enough_items and precise_enough):
        result = await _finalize(session, test_session, estimate)
        return AnswerOutcome(correct=correct, next_item=None, finished=True, result=result)

    used = [r.item_id for r in responses]
    nxt = select_next_item(list(items_map.values()), estimate.theta, used_item_ids=used)
    if nxt is None:
        result = await _finalize(session, test_session, estimate)
        return AnswerOutcome(correct=correct, next_item=None, finished=True, result=result)

    next_item = next(i for i in items if i.id == nxt.id)
    next_item.exposure_count += 1
    await session.commit()
    return AnswerOutcome(correct=correct, next_item=public_item(next_item), finished=False)


async def _load_responses(session: AsyncSession, session_id: str) -> List[ItemResponseRecord]:
    result = await session.execute(
        select(ItemResponseRecord)
        .where(ItemResponseRecord.session_id == session_id)
        .order_by(ItemResponseRecord.created_at)
    )
    return list(result.scalars().all())


async def _finalize(
    session: AsyncSession, test_session: TestSession, estimate: AbilityEstimate
) -> Dict[str, Any]:
    """Завершает тест: определяет грейд, присваивает категорию, применяет правила смены."""
    result_grade = grade_for_theta(estimate.theta)
    test_session.result_grade = result_grade
    test_session.status = SESSION_COMPLETED
    test_session.finished_at = utcnow()

    warnings = list(test_session.warnings or [])
    for warning in estimate.warnings:
        if warning not in warnings:
            warnings.append(warning)
    test_session.warnings = warnings

    category = await _get_or_create_category(
        session, test_session.specialization_id, result_grade
    )
    test_session.category_id = category.id

    profile = await _ensure_profile(session, test_session.user_id)
    grade_outcome = await _apply_grade_rule(session, profile, test_session, result_grade)
    specialization = await session.get(Specialization, test_session.specialization_id)
    if specialization is not None:
        profile.specialization = specialization.code
    test_session.grade_applied = bool(grade_outcome["applied"])

    await session.commit()
    await session.refresh(test_session)

    return {
        "session_id": test_session.id,
        "status": test_session.status,
        "items_answered": test_session.item_count,
        "theta": estimate.theta,
        "standard_error": estimate.standard_error,
        "converged": estimate.converged,
        "result_grade": result_grade,
        "category_id": category.id,
        "specialization": specialization.code if specialization else None,
        "current_grade": profile.grade,
        "grade_change_applied": grade_outcome["applied"],
        "grade_change_reason": grade_outcome["reason"],
        "warnings": warnings,
    }


async def _get_or_create_category(
    session: AsyncSession, specialization_id: int, grade_code: str
) -> Category:
    result = await session.execute(
        select(Category).where(
            Category.specialization_id == specialization_id, Category.grade_code == grade_code
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        category = Category(specialization_id=specialization_id, grade_code=grade_code)
        session.add(category)
        await session.flush()
    return category


async def _apply_grade_rule(
    session: AsyncSession, profile: CandidateProfile, test_session: TestSession, result_grade: str
) -> Dict[str, Any]:
    """Применяет правила смены грейда. Возвращает {applied, reason}."""
    current = profile.grade

    if current is None:
        profile.grade = result_grade
        session.add(
            GradeChange(user_id=profile.user_id, from_grade=None, to_grade=result_grade,
                        session_id=test_session.id)
        )
        return {"applied": True, "reason": "первичное присвоение грейда"}

    if result_grade == current:
        return {"applied": False, "reason": "результат совпал с текущим грейдом"}

    if GRADE_ORDER.index(result_grade) < GRADE_ORDER.index(current):
        return {
            "applied": False,
            "reason": "понижение грейда не применяется автоматически — текущий грейд сохранён",
        }

    last_change = (
        await session.execute(
            select(GradeChange)
            .where(GradeChange.user_id == profile.user_id)
            .order_by(GradeChange.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    days_since = None
    if last_change is not None:
        days_since = (utcnow() - last_change.created_at).days

    cooldown = get_settings().grade_change_cooldown_days
    allowed, remaining = can_change_grade(days_since, cooldown)
    if not allowed:
        return {
            "applied": False,
            "reason": f"смена грейда ограничена по времени: доступна через {remaining} дн.",
        }

    profile.grade = result_grade
    session.add(
        GradeChange(user_id=profile.user_id, from_grade=current, to_grade=result_grade,
                    session_id=test_session.id)
    )
    return {"applied": True, "reason": f"повышение грейда: {current} → {result_grade}"}


async def current_category(session: AsyncSession, user_id: str) -> Dict[str, Any]:
    """Текущий статус кандидата: специализация, грейд, история и ограничение смены."""
    profile = await _ensure_profile(session, user_id)

    history = (
        await session.execute(
            select(GradeChange)
            .where(GradeChange.user_id == user_id)
            .order_by(GradeChange.created_at.desc())
        )
    ).scalars().all()

    sessions = (
        await session.execute(
            select(TestSession)
            .where(TestSession.user_id == user_id)
            .order_by(TestSession.started_at.desc())
        )
    ).scalars().all()

    last_change_days = None
    if history:
        last_change_days = (utcnow() - history[0].created_at).days
    cooldown = get_settings().grade_change_cooldown_days
    allowed, remaining = can_change_grade(last_change_days, cooldown)

    return {
        "specialization": profile.specialization,
        "grade": profile.grade,
        "grade_change_allowed": allowed,
        "grade_change_available_in_days": remaining,
        "grade_change_cooldown_days": cooldown,
        "grade_options": next_grade_options(profile.grade or "junior"),
        "grade_history": [
            {"from_grade": h.from_grade, "to_grade": h.to_grade, "at": h.created_at}
            for h in history
        ],
        "sessions": [
            {
                "id": s.id,
                "status": s.status,
                "target_grade": s.target_grade,
                "result_grade": s.result_grade,
                "items_answered": s.item_count,
                "theta": s.theta,
            }
            for s in sessions
        ],
    }
