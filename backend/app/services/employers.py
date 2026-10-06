"""Бизнес-логика кабинета работодателя: потребность, подборка, поиск по банку.

Подборка строится на категориях (специализация × грейд), а не на самоописании
резюме. Внутри подборки кандидаты ранжируются рубрикой из `app.services.matching`,
и каждый получает объяснение попадания.

Контакты кандидата в карточку не попадают вовсе: раскрытие выполняется отдельно
после принятия приглашения или самостоятельного отклика (Этап 5).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.models.candidate import DEFAULT_PRIVACY, CandidateProfile
from app.models.employer import EmployerNeed, EmployerProfile, Selection, SelectionCandidate
from app.models.testing import SESSION_COMPLETED, Category, TestSession
from app.models.user import User, UserRole
from app.providers.registry import get_fsp
from app.schemas.employer import EmployerProfileIn, NeedIn, SearchQuery
from app.services import reference
from app.services.fit import (
    compute_fit,
    days_since,
    matched_stack,
    normalize_theta,
)
from app.services.matching import (
    RUBRIC_VERSION,
    CandidateSignals,
    rank_candidates,
    score_candidate,
)
from app.services.testing import GRADE_ORDER

logger = logging.getLogger(__name__)

MAX_SELECTION_CANDIDATES = 25


class EmployerError(DomainError):
    """Ошибка стороны работодателя: профиль, потребность, поиск."""


# --- Профиль компании ---------------------------------------------------------


async def get_profile(session: AsyncSession, user_id: str) -> EmployerProfile | None:
    result = await session.execute(select(EmployerProfile).where(EmployerProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_profile(session: AsyncSession, user_id: str, data: EmployerProfileIn) -> EmployerProfile:
    profile = await get_profile(session, user_id)
    if profile is None:
        profile = EmployerProfile(user_id=user_id)
        session.add(profile)
        await session.flush()
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


# --- Потребность --------------------------------------------------------------


async def create_need(session: AsyncSession, user_id: str, payload: NeedIn) -> EmployerNeed:
    specialization = await reference.specialization_by_code(session, payload.specialization_code)
    if payload.specialization_code and specialization is None:
        raise EmployerError(404, "Специализация не найдена")
    specialization_id = specialization.id if specialization else None

    if payload.grade and payload.grade not in GRADE_ORDER:
        raise EmployerError(400, "Неизвестный грейд")
    if payload.salary_from and payload.salary_to and payload.salary_from > payload.salary_to:
        raise EmployerError(400, "Нижняя граница зарплаты больше верхней")

    need = EmployerNeed(
        employer_id=user_id,
        title=payload.title,
        description=payload.description,
        specialization_id=specialization_id,
        grade_code=payload.grade,
        stack=list(payload.stack),
        salary_from=payload.salary_from,
        salary_to=payload.salary_to,
    )
    session.add(need)
    await session.commit()
    await session.refresh(need)
    return need


# --- Банк кандидатов ----------------------------------------------------------


async def _candidate_rows(
    session: AsyncSession,
    *,
    specialization_code: str | None = None,
    grade: str | None = None,
    category_id: int | None = None,
    stack: Sequence[str] = (),
    has_fsp: bool | None = None,
) -> list[tuple[CandidateProfile, User]]:
    """Кандидаты банка: только прошедшие тест (у них определён грейд)."""
    query = (
        select(CandidateProfile, User)
        .join(User, User.id == CandidateProfile.user_id)
        .where(
            User.role == UserRole.CANDIDATE,
            User.is_active.is_(True),
            CandidateProfile.grade.is_not(None),
        )
    )
    if specialization_code:
        query = query.where(CandidateProfile.specialization == specialization_code)
    if grade:
        query = query.where(CandidateProfile.grade == grade)
    if has_fsp is True:
        query = query.where(User.fsp_id.is_not(None))
    elif has_fsp is False:
        query = query.where(User.fsp_id.is_(None))
    if category_id is not None:
        category = await session.get(Category, category_id)
        if category is None:
            return []
        code = await reference.specialization_code(session, category.specialization_id)
        query = query.where(
            CandidateProfile.specialization == code,
            CandidateProfile.grade == category.grade_code,
        )

    rows = list((await session.execute(query)).all())

    if stack:
        wanted = {s.strip().lower() for s in stack if s and s.strip()}
        rows = [(p, u) for (p, u) in rows if wanted & {s.strip().lower() for s in (p.stack or [])}]
    return rows


async def _signals_for(
    session: AsyncSession,
    profile: CandidateProfile,
    user: User,
    *,
    required_stack: Sequence[str],
    required_specialization: str | None,
    required_grade: str | None,
    in_requested_category: bool | None = None,
) -> tuple[CandidateSignals, dict[str, Any]]:
    """Сигналы кандидата: сила теста, достижения ФСП, свежесть, соответствие."""
    last_session = (
        await session.execute(
            select(TestSession)
            .where(
                TestSession.user_id == user.id,
                TestSession.status == SESSION_COMPLETED,
            )
            .order_by(TestSession.finished_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    theta = last_session.theta if last_session is not None else None
    test_strength = normalize_theta(theta)

    # Свежесть профиля: учитываются и завершённый тест, и участие в регулярных заданиях
    from app.services.marketplace import last_activity_at

    last_activity = await last_activity_at(session, user.id)
    fresh_days = days_since(last_activity)

    fsp_count: int | None = None
    if user.fsp_id:
        try:
            achievements = await get_fsp().fetch_achievements(user.fsp_id)
            fsp_count = len(achievements)
        except Exception as exc:  # noqa: BLE001 — недоступность реестра не должна ломать подборку
            logger.warning("не удалось получить достижения ФСП: %s", exc)
            fsp_count = None

    fit = compute_fit(
        required_stack=required_stack,
        candidate_stack=profile.stack or [],
        required_specialization=required_specialization,
        candidate_specialization=profile.specialization,
        required_grade=required_grade,
        candidate_grade=profile.grade,
        grade_order=GRADE_ORDER,
    )

    signals = CandidateSignals(
        candidate_id=user.id,
        test_strength=test_strength,
        fsp_achievements=fsp_count,
        days_since_last_task=fresh_days,
        semantic_fit=fit,
        in_requested_category=in_requested_category,
    )
    debug = {
        "theta": theta,
        "matched_stack": matched_stack(required_stack, profile.stack or []),
        "fsp_id_present": bool(user.fsp_id),
    }
    return signals, debug


def _mask(profile: CandidateProfile, privacy: dict[str, bool]) -> dict[str, bool]:
    return {
        "stack": privacy.get("show_stack", True),
        "experience": privacy.get("show_experience", True),
        "fsp": privacy.get("show_fsp", True),
    }


async def search_candidates(session: AsyncSession, query: SearchQuery) -> tuple[int, list[dict[str, Any]]]:
    """Поиск по банку кандидатов с фильтрами и объяснимым ранжированием."""
    rows = await _candidate_rows(
        session,
        specialization_code=query.specialization_code,
        grade=query.grade,
        category_id=query.category_id,
        stack=query.stack,
        has_fsp=query.has_fsp,
    )

    scored: list[tuple[Any, CandidateProfile, User, dict[str, Any], CandidateSignals]] = []
    for profile, user in rows:
        # Соответствие запрошенной категории: выдача строится по категориям,
        # поэтому такие кандидаты получают приоритет в порядке выдачи.
        category_match: bool | None = None
        if query.specialization_code or query.grade:
            category_match = (
                not query.specialization_code or profile.specialization == query.specialization_code
            ) and (not query.grade or profile.grade == query.grade)
        signals, debug = await _signals_for(
            session,
            profile,
            user,
            required_stack=query.stack,
            required_specialization=query.specialization_code,
            required_grade=query.grade,
            in_requested_category=category_match,
        )
        scored.append((score_candidate(signals), profile, user, debug, signals))

    scored.sort(
        key=lambda item: (
            not bool(item[4].in_requested_category),
            -item[0].score,
            item[2].id,
        )
    )
    total = len(scored)
    page = scored[query.offset : query.offset + query.limit]

    candidates = [
        _card(item[0], item[1], item[2], rank=query.offset + index)
        for index, item in enumerate(page, start=1)
    ]
    return total, candidates


def _fsp_from_reasons(reasons: Sequence[Any]) -> int | None:
    """Извлекает число подтверждённых достижений из объяснения ранжирования."""
    for reason in reasons:
        code = reason.get("code") if isinstance(reason, dict) else getattr(reason, "code", None)
        if code != "fsp_achievements":
            continue
        text = reason.get("text") if isinstance(reason, dict) else getattr(reason, "text", "")
        digits = "".join(ch for ch in str(text) if ch.isdigit())
        return int(digits) if digits else 0
    return None


def _card(scored: Any, profile: CandidateProfile, user: User, *, rank: int) -> dict[str, Any]:
    """Карточка кандидата без контактов; приватность ограничивает видимые блоки."""
    privacy = {**DEFAULT_PRIVACY, **(profile.privacy or {})}
    visible = _mask(profile, privacy)
    return {
        "reference": reference.candidate_reference(user.id),
        "full_name": profile.full_name,
        "specialization": profile.specialization,
        "grade": profile.grade,
        "category_id": None,
        "stack": list(profile.stack or []) if visible["stack"] else [],
        "experience_years": profile.experience_years if visible["experience"] else None,
        "fsp_achievements": _fsp_from_reasons(scored.reasons) if visible["fsp"] else None,
        "summary": profile.summary,
        "contacts_visible": False,
        "rank": rank,
        "score": scored.score,
        "reasons": [
            {"code": r.code, "text": r.text, "value": r.value, "contribution": r.contribution}
            for r in scored.reasons
            if r.code != "rank"
        ],
        "missing": scored.missing,
    }


async def _category_id(
    session: AsyncSession, specialization_code: str | None, grade: str | None
) -> int | None:
    if not specialization_code or not grade:
        return None
    specialization = await reference.specialization_by_code(session, specialization_code)
    if specialization is None:
        return None
    category = (
        await session.execute(
            select(Category).where(
                Category.specialization_id == specialization.id,
                Category.grade_code == grade,
            )
        )
    ).scalar_one_or_none()
    return category.id if category else None


async def _recommended_categories(
    session: AsyncSession, specialization_id: int | None, grade: str | None
) -> list[Category]:
    """Рекомендуемые категории: целевая и соседние по грейду."""
    if specialization_id is None or not grade:
        return []
    index = GRADE_ORDER.index(grade) if grade in GRADE_ORDER else 0
    neighbour_grades = {
        grade,
        GRADE_ORDER[max(0, index - 1)],
        GRADE_ORDER[min(len(GRADE_ORDER) - 1, index + 1)],
    }
    result = await session.execute(
        select(Category).where(
            Category.specialization_id == specialization_id,
            Category.grade_code.in_(neighbour_grades),
        )
    )
    categories = list(result.scalars().all())
    categories.sort(key=lambda c: (c.grade_code != grade, GRADE_ORDER.index(c.grade_code)))
    return categories


async def build_selection(
    session: AsyncSession,
    employer_id: str,
    need: EmployerNeed,
    *,
    parent_selection_id: str | None = None,
    stack_override: Sequence[str] | None = None,
    grade_override: str | None = None,
    title: str | None = None,
) -> tuple[Selection, list[SelectionCandidate]]:
    """Формирует подборку по потребности и сохраняет её вместе с объяснениями."""
    specialization_code = None
    if need.specialization_id:
        specialization_code = await reference.specialization_code(session, need.specialization_id)

    grade = grade_override or need.grade_code
    required_stack = list(stack_override if stack_override is not None else (need.stack or []))

    categories = await _recommended_categories(session, need.specialization_id, grade)
    category_ids = [c.id for c in categories]
    grade_by_category = {c.id: c.grade_code for c in categories}

    rows = await _candidate_rows(session, specialization_code=specialization_code, stack=required_stack)
    # Оставляем кандидатов рекомендуемых категорий; если их мало — добираем остальных
    primary: list[tuple[CandidateProfile, User]] = []
    secondary: list[tuple[CandidateProfile, User]] = []
    for profile, user in rows:
        if grade and profile.grade in grade_by_category.values():
            primary.append((profile, user))
        else:
            secondary.append((profile, user))

    ordered = primary if len(primary) >= 5 else primary + secondary[: max(0, 5 - len(primary))]

    signals: list[CandidateSignals] = []
    debug_map: dict[str, dict[str, Any]] = {}
    profiles: dict[str, tuple[CandidateProfile, User]] = {}
    for profile, user in ordered[:MAX_SELECTION_CANDIDATES]:
        prepared, debug = await _signals_for(
            session,
            profile,
            user,
            required_stack=required_stack,
            required_specialization=specialization_code,
            required_grade=grade,
            in_requested_category=(None if not grade else profile.grade in grade_by_category.values()),
        )
        signals.append(prepared)
        debug_map[user.id] = debug
        profiles[user.id] = (profile, user)

    ranked = rank_candidates(signals)

    selection = Selection(
        employer_id=employer_id,
        need_id=need.id,
        parent_selection_id=parent_selection_id,
        title=title or need.title,
        params={
            "specialization": specialization_code,
            "grade": grade,
            "stack": required_stack,
            "recommended_categories": category_ids,
        },
        rubric_version=RUBRIC_VERSION,
    )
    session.add(selection)
    await session.flush()

    stored: list[SelectionCandidate] = []
    for position, scored in enumerate(ranked, start=1):
        profile, user = profiles[scored.candidate_id]
        record = SelectionCandidate(
            selection_id=selection.id,
            candidate_user_id=user.id,
            category_id=await _category_id(session, profile.specialization, profile.grade),
            rank=position,
            score=scored.score,
            reasons=[
                {"code": r.code, "text": r.text, "value": r.value, "contribution": r.contribution}
                for r in scored.reasons
            ],
            missing=scored.missing,
        )
        session.add(record)
        stored.append(record)

    await session.commit()
    await session.refresh(selection)
    return selection, stored


async def get_selection(
    session: AsyncSession, employer_id: str, selection_id: str
) -> tuple[Selection, list[tuple[SelectionCandidate, CandidateProfile, User]]]:
    selection = await session.get(Selection, selection_id)
    if selection is None or selection.employer_id != employer_id:
        raise EmployerError(404, "Подборка не найдена")

    records = list(
        (
            await session.execute(
                select(SelectionCandidate)
                .where(SelectionCandidate.selection_id == selection_id)
                .order_by(SelectionCandidate.rank)
            )
        )
        .scalars()
        .all()
    )

    enriched: list[tuple[SelectionCandidate, CandidateProfile, User]] = []
    for record in records:
        profile = (
            await session.execute(
                select(CandidateProfile).where(CandidateProfile.user_id == record.candidate_user_id)
            )
        ).scalar_one_or_none()
        user = await session.get(User, record.candidate_user_id)
        if profile is not None and user is not None:
            enriched.append((record, profile, user))
    return selection, enriched


async def list_selections(session: AsyncSession, employer_id: str) -> list[tuple[Selection, int]]:
    selections = list(
        (
            await session.execute(
                select(Selection)
                .where(Selection.employer_id == employer_id)
                .order_by(Selection.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    counts = dict(
        (
            await session.execute(
                select(SelectionCandidate.selection_id, func.count()).group_by(
                    SelectionCandidate.selection_id
                )
            )
        ).all()
    )
    return [(s, int(counts.get(s.id, 0))) for s in selections]


def selection_candidate_card(
    record: SelectionCandidate, profile: CandidateProfile, user: User
) -> dict[str, Any]:
    privacy = {**DEFAULT_PRIVACY, **(profile.privacy or {})}
    visible = _mask(profile, privacy)
    return {
        "reference": reference.candidate_reference(user.id),
        "full_name": profile.full_name,
        "specialization": profile.specialization,
        "grade": profile.grade,
        "category_id": record.category_id,
        "stack": list(profile.stack or []) if visible["stack"] else [],
        "experience_years": profile.experience_years if visible["experience"] else None,
        "fsp_achievements": _fsp_from_reasons(record.reasons) if visible["fsp"] else None,
        "summary": profile.summary,
        "contacts_visible": False,
        "rank": record.rank,
        "score": record.score,
        "reasons": record.reasons or [],
        "missing": record.missing or [],
    }
