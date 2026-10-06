"""Подсказки по накопленным платформой сигналам: что предложить каждой стороне.

Идея — снизить ручную работу: кандидату показываются вакансии, близкие к тому, что
он уже выбрал и к его категории; компании — кандидаты, близкие к её собственным
действиям (потребности, приглашения, вакансии), которых она ещё не приглашала.

Важно про «дообучение»: модель не дообучается. Ранжирование строится на сигналах,
которые платформа накопила о конкретном пользователе (профиль, категория, отклики,
приглашения, стек потребностей), плюс семантическая близость через эмбеддинги. Это
объяснимо и воспроизводимо: у каждой позиции показано, почему она предложена.
Модель подключается только для формулировки вывода словами и не считает числа.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import utcnow
from app.models.candidate import CandidateProfile
from app.models.employer import EmployerNeed, EmployerProfile
from app.models.invitation import STATUS_ACCEPTED, STATUS_SENT, STATUS_VIEWED, Invitation
from app.models.marketplace import VACANCY_PUBLISHED, Application, Vacancy
from app.models.user import User, UserRole
from app.services import reference
from app.services.testing import GRADE_ORDER

# Веса подсказок. Ядро решения не меняют: это надстройка над подбором, а не замена.
W_CATEGORY = 0.45
W_STACK = 0.20
W_SEMANTIC = 0.20
W_FRESHNESS = 0.15

ACTIVE_INVITATION_STATUSES = (STATUS_SENT, STATUS_VIEWED, STATUS_ACCEPTED)


def _stack_overlap(left: list[str], right: list[str]) -> tuple[float, list[str]]:
    """Доля совпавших технологий и их список — для объяснения «почему предложено»."""
    a = {item.strip().lower() for item in left if item and item.strip()}
    b = {item.strip().lower() for item in right if item and item.strip()}
    if not a or not b:
        return 0.0, []
    common = sorted(a & b)
    return len(common) / len(a | b), common


def _grade_distance(left: str | None, right: str | None) -> int | None:
    """Насколько грейды далеки друг от друга (0 — совпадают)."""
    if left not in GRADE_ORDER or right not in GRADE_ORDER:
        return None
    return abs(GRADE_ORDER.index(left) - GRADE_ORDER.index(right))


def _freshness_score(days: int, full_days: int = 30, zero_days: int = 180) -> float:
    if days <= full_days:
        return 1.0
    if days >= zero_days:
        return 0.0
    return round((zero_days - days) / (zero_days - full_days), 3)


async def _semantic(anchor_text: str, texts: list[str]) -> tuple[list[float], str]:
    """Семантическая близость через эмбеддинги; при недоступности — нули."""
    if not texts or not anchor_text.strip():
        return [0.0] * len(texts), "не применялась"
    if not get_settings().semantic_match_enabled:
        # Переключатель SEMANTIC_MATCH_ENABLED выключает обращения к модели:
        # подсказки остаются на сигналах платформы и честно об этом сообщают.
        return [0.0] * len(texts), "выключена настройкой"
    from app.services.ai import get_ai

    result = await get_ai().semantic_scores(anchor_text, texts)
    scores = list(result.data.get("scores") or [])
    if len(scores) != len(texts):
        return [0.0] * len(texts), "недоступно"
    return [float(item) for item in scores], str(result.data.get("method") or "эмбеддинги")


# --- Кандидат: близкие вакансии -------------------------------------------------


async def vacancy_hints(session: AsyncSession, candidate_user_id: str, limit: int = 5) -> dict[str, Any]:
    """Вакансии, близкие к профилю, категории и уже выбранным кандидатом вакансиям."""
    profile = (
        await session.execute(select(CandidateProfile).where(CandidateProfile.user_id == candidate_user_id))
    ).scalar_one_or_none()

    applications = (
        (await session.execute(select(Application).where(Application.candidate_user_id == candidate_user_id)))
        .scalars()
        .all()
    )
    applied_ids = {item.vacancy_id for item in applications}

    vacancies = (
        (await session.execute(select(Vacancy).where(Vacancy.status == VACANCY_PUBLISHED))).scalars().all()
    )
    vacancies = [item for item in vacancies if item.id not in applied_ids]
    if not vacancies:
        return {
            "items": [],
            "anchor": "none",
            "semantic_method": "не применялась",
            "note": "Нет опубликованных вакансий, которые вы ещё не рассматривали.",
        }

    codes, titles = await reference.specialization_maps(session)

    # Опорный текст: сначала выбранные вакансии (интерес), иначе сам профиль.
    anchor_kind = "profile"
    anchor_text = " ".join(
        filter(
            None,
            [
                profile.summary if profile else None,
                " ".join(profile.stack) if profile else None,
                profile.specialization if profile else None,
            ],
        )
    )
    if applications:
        applied_vacancies = [
            item
            for item in (await session.execute(select(Vacancy))).scalars().all()
            if item.id in applied_ids
        ]
        if applied_vacancies:
            anchor_kind = "applications"
            anchor_text = " ".join(
                f"{item.title} {item.description or ''} {' '.join(item.stack or [])}"
                for item in applied_vacancies
            )

    texts = [f"{item.title} {item.description or ''} {' '.join(item.stack or [])}" for item in vacancies]
    semantic, method = await _semantic(anchor_text, texts)

    now = utcnow()
    scored: list[dict[str, Any]] = []
    for index, vacancy in enumerate(vacancies):
        reasons: list[str] = []
        code = codes.get(vacancy.specialization_id) if vacancy.specialization_id else None

        category_score = 0.0
        if profile and profile.specialization and code == profile.specialization:
            if vacancy.grade_code and vacancy.grade_code == profile.grade:
                category_score = 1.0
                reasons.append("совпадают специализация и грейд")
            elif vacancy.grade_code:
                distance = _grade_distance(profile.grade, vacancy.grade_code)
                if distance is not None and distance <= 1:
                    category_score = 0.6
                    reasons.append(f"соседний грейд: {titles.get(code or '', code or 'направление')}")
                else:
                    category_score = 0.3
                    reasons.append("совпадает специализация")
            else:
                category_score = 0.7
                reasons.append("совпадает специализация, грейд не указан")

        stack_score, common = _stack_overlap(profile.stack if profile else [], vacancy.stack or [])
        if common:
            reasons.append("совпадает стек: " + ", ".join(common[:4]))

        semantic_score = semantic[index] if index < len(semantic) else 0.0
        if semantic_score >= 0.35 and anchor_kind == "applications":
            reasons.append("похожа на вакансии, которые вы уже выбирали")

        created = vacancy.created_at
        days = (now - created).days if created else 999
        fresh_score = _freshness_score(days)
        if days <= 30:
            reasons.append("опубликована недавно")

        score = (
            W_CATEGORY * category_score
            + W_STACK * stack_score
            + W_SEMANTIC * semantic_score
            + W_FRESHNESS * fresh_score
        )
        if not reasons:
            reasons.append("совпадений по профилю не нашлось — показана как вариант для расширения поиска")

        scored.append(
            {
                "id": vacancy.id,
                "title": vacancy.title,
                "company_name": None,
                "salary_from": vacancy.salary_from,
                "salary_to": vacancy.salary_to,
                "specialization": code,
                "grade": vacancy.grade_code,
                "stack": list(vacancy.stack or []),
                "score": round(score, 4),
                "reasons": reasons,
            }
        )

    scored.sort(key=lambda item: -item["score"])
    top = scored[:limit]

    companies = {
        row.user_id: row.company_name
        for row in (await session.execute(select(EmployerProfile))).scalars().all()
    }
    vacancy_owner = {item.id: item.employer_id for item in vacancies}
    for item in top:
        item["company_name"] = companies.get(vacancy_owner.get(item["id"], ""))

    return {
        "items": top,
        "anchor": anchor_kind,
        "semantic_method": method,
        "note": (
            "Показаны вакансии, близкие к уже выбранным вами"
            if anchor_kind == "applications"
            else "Вы ещё не откликались — показаны вакансии, близкие к вашему профилю и категории"
        ),
    }


# --- Работодатель: потенциальные кандидаты --------------------------------------


async def candidate_hints(session: AsyncSession, employer_id: str, limit: int = 5) -> dict[str, Any]:
    """Кандидаты, близкие к действиям компании и ещё не приглашённые ею."""
    needs = (
        (await session.execute(select(EmployerNeed).where(EmployerNeed.employer_id == employer_id)))
        .scalars()
        .all()
    )
    invitations = (
        (await session.execute(select(Invitation).where(Invitation.employer_id == employer_id)))
        .scalars()
        .all()
    )
    invited_ids = {item.candidate_user_id for item in invitations}
    active_ids = {item.candidate_user_id for item in invitations if item.status in ACTIVE_INVITATION_STATUSES}

    if not needs and not invitations:
        return {
            "items": [],
            "anchor": "none",
            "semantic_method": "не применялась",
            "note": "Пока нет ваших действий: опишите потребность или отправьте первое приглашение.",
        }

    codes, titles = await reference.specialization_maps(session)

    wanted: list[tuple[str | None, str | None]] = [
        (codes.get(need.specialization_id) if need.specialization_id else None, need.grade_code)
        for need in needs
    ]
    wanted_stacks: list[str] = []
    for need in needs:
        wanted_stacks.extend(need.stack or [])

    profiles = (await session.execute(select(CandidateProfile))).scalars().all()
    users = {
        row.id: row
        for row in (await session.execute(select(User).where(User.role == UserRole.CANDIDATE)))
        .scalars()
        .all()
    }
    candidates = [item for item in profiles if item.user_id in users and item.user_id not in active_ids]
    if not candidates:
        return {
            "items": [],
            "anchor": "none",
            "semantic_method": "не применялась",
            "note": "Все подходящие кандидаты уже получили ваше приглашение.",
        }

    # Опорный текст: профили тех, кого компания уже приглашала (её собственный вкус).
    anchor_kind = "needs"
    anchor_text = " ".join(filter(None, [" ".join(wanted_stacks), " ".join(str(w) for w in wanted if w[0])]))
    if invited_ids:
        anchor_profiles = [item for item in profiles if item.user_id in invited_ids]
        if anchor_profiles:
            anchor_kind = "invitations"
            anchor_text = " ".join(
                f"{item.full_name or ''} {item.summary or ''} {' '.join(item.stack or [])}"
                for item in anchor_profiles
            )

    texts = [
        f"{item.full_name or ''} {item.summary or ''} {' '.join(item.stack or [])}" for item in candidates
    ]
    semantic, method = await _semantic(anchor_text, texts)

    now = utcnow()
    scored: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        reasons: list[str] = []

        category_score = 0.0
        for code, grade in wanted:
            if code and candidate.specialization == code:
                if grade and candidate.grade == grade:
                    category_score = 1.0
                    reasons.append("точно та категория, которую вы описали в потребности")
                    break
                if grade:
                    distance = _grade_distance(candidate.grade, grade)
                    if distance is not None and distance <= 1:
                        category_score = max(category_score, 0.6)
                        reasons.append(f"соседний грейд: {titles.get(code or '', code or 'направление')}")
                        break
                category_score = max(category_score, 0.7)
                reasons.append("совпадает специализация с вашей потребностью")
                break

        stack_score, common = _stack_overlap(candidate.stack, wanted_stacks)
        if common:
            reasons.append("совпадает стек потребности: " + ", ".join(common[:4]))

        semantic_score = semantic[index] if index < len(semantic) else 0.0
        if semantic_score >= 0.35 and anchor_kind == "invitations":
            reasons.append("похож на тех кандидатов, кого вы приглашали")

        days = (now - candidate.updated_at).days if candidate.updated_at else 999
        fresh_score = _freshness_score(days)
        if days <= 30:
            reasons.append("профиль активен в последний месяц")

        score = (
            W_CATEGORY * category_score
            + W_STACK * stack_score
            + W_SEMANTIC * semantic_score
            + W_FRESHNESS * fresh_score
        )
        if not reasons:
            reasons.append("прямых совпадений нет — кандидат вне ваших текущих запросов")

        scored.append(
            {
                "reference": reference.candidate_reference(candidate.user_id),
                "full_name": candidate.full_name,
                "specialization": candidate.specialization,
                "grade": candidate.grade,
                "stack": list(candidate.stack or []),
                "score": round(score, 4),
                "reasons": reasons,
                "already_invited": candidate.user_id in invited_ids,
            }
        )

    scored.sort(key=lambda item: -item["score"])
    return {
        "items": scored[:limit],
        "anchor": anchor_kind,
        "semantic_method": method,
        "note": (
            "Кандидаты подобраны по вашим приглашениям и потребностям"
            if anchor_kind == "invitations"
            else "Кандидаты подобраны по описанным вами потребностям"
        ),
    }
