"""ИИ-эндпоинты: автоматизация рутинных действий поверх локальной модели.

Модуль **не заменяет** основные сценарии, а дополняет их: кандидат может
заполнить профиль вручную, работодатель — описать потребность сам. ИИ лишь
ускоряет эти действия и всегда возвращает признак `degraded`, показывая, была
ли задействована модель или отданы демо-данные.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.user import User, UserRole
from app.schemas.ai import (
    AIResultOut,
    AIStatusOut,
    CoverLetterIn,
    InvitationDraftIn,
    MatchExplainIn,
    NeedDraftIn,
    ProfileAnalyzeIn,
    SemanticScoresIn,
    TaskDraftIn,
)
from app.services import employers as employer_service
from app.services import suggest as suggestion
from app.services.ai import AIError, get_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

candidate_only = require_roles(UserRole.CANDIDATE)
employer_only = require_roles(UserRole.EMPLOYER)
any_user = require_roles(UserRole.CANDIDATE, UserRole.EMPLOYER)
# Состояние модели показывается в шапке каждого кабинета, поэтому его читает и
# администратор: это справка, а не ИИ-действие над данными.
status_reader = require_roles(UserRole.CANDIDATE, UserRole.EMPLOYER, UserRole.ADMIN)


@router.get("/status", response_model=AIStatusOut, summary="Состояние ИИ-слоя")
async def ai_status(user: User = Depends(status_reader)) -> AIStatusOut:
    """Показывает, какая модель активна и не работаем ли мы на демо-данных."""
    state = await get_ai().status()
    if state.get("available"):
        hint = f"Работает локальная модель {state.get('model')} — данные не покидают контур"
    else:
        hint = "Модель недоступна: платформа работает на демо-данных, основной путь не затронут"
    return AIStatusOut(**state, hint=hint)


@router.post(
    "/profile/analyze",
    response_model=AIResultOut,
    summary="Разбор профиля или резюме: поля и подсказки",
)
async def analyze_profile(
    payload: ProfileAnalyzeIn,
    user: User = Depends(candidate_only),
) -> AIResultOut:
    """Извлекает стек, роли и стаж из текста и предлагает, что дополнить."""
    result = await get_ai().analyze_profile(payload.text)
    return AIResultOut(**result.as_dict())


@router.post(
    "/need/draft",
    response_model=AIResultOut,
    summary="Черновик описания потребности по краткой заметке",
)
async def draft_need(payload: NeedDraftIn, user: User = Depends(employer_only)) -> AIResultOut:
    """Превращает короткую заметку в структурированную потребность."""
    result = await get_ai().draft_need(payload.brief)
    return AIResultOut(**result.as_dict())


@router.post(
    "/invitation/draft",
    response_model=AIResultOut,
    summary="Черновик текста приглашения кандидату",
)
async def draft_invitation(payload: InvitationDraftIn, user: User = Depends(employer_only)) -> AIResultOut:
    """Готовит текст предложения; зарплата и компания подставляются из данных формы."""
    result = await get_ai().draft_invitation(
        company=payload.company,
        candidate_grade=payload.candidate_grade,
        stack=payload.stack,
        salary_from=payload.salary_from,
        salary_to=payload.salary_to,
        role_title=payload.role_title,
    )
    return AIResultOut(**result.as_dict())


@router.post(
    "/cover-letter",
    response_model=AIResultOut,
    summary="Сопроводительное письмо под вакансию",
)
async def cover_letter(payload: CoverLetterIn, user: User = Depends(candidate_only)) -> AIResultOut:
    """Пишет письмо, опираясь на реальное пересечение стека, без выдуманного опыта."""
    result = await get_ai().draft_cover_letter(
        vacancy_title=payload.vacancy_title,
        company=payload.company,
        required_stack=payload.required_stack,
        candidate_stack=payload.candidate_stack,
        candidate_grade=payload.candidate_grade,
    )
    return AIResultOut(**result.as_dict())


@router.post(
    "/match/explain",
    response_model=AIResultOut,
    summary="Объяснение попадания кандидата в подборку человеческим языком",
)
async def explain_match(
    payload: MatchExplainIn,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> AIResultOut:
    """Формулирует объяснение на основе уже сохранённых критериев ранжирования."""
    selection, rows = await employer_service.get_selection(session, user.id, payload.selection_id)

    target = None
    for record, profile, candidate_user in rows:
        card = employer_service.selection_candidate_card(record, profile, candidate_user)
        if card["reference"] == payload.candidate_reference:
            target = card
            break
    if target is None:
        raise AIError(404, "Кандидат не найден в указанной подборке")

    params = selection.params or {}
    need_summary = selection.title
    if isinstance(params.get("stack"), list) and params["stack"]:
        need_summary += f". Требуемый стек: {', '.join(map(str, params['stack']))}"

    candidate_summary = (
        f"{target.get('specialization') or 'специализация не указана'}, "
        f"грейд {target.get('grade') or 'не определён'}, "
        f"стек: {', '.join(target.get('stack') or []) or 'не указан'}"
    )

    result = await get_ai().explain_match(
        candidate_summary=candidate_summary,
        need_summary=need_summary,
        reasons=list(target.get("reasons") or []),
    )
    data = dict(result.data)
    data["missing"] = list(target.get("missing") or [])
    result.data = data
    return AIResultOut(**result.as_dict())


@router.post(
    "/task/draft",
    response_model=AIResultOut,
    summary="Заготовка короткого регулярного задания",
)
async def draft_task(payload: TaskDraftIn, user: User = Depends(employer_only)) -> AIResultOut:
    """Составляет короткое практическое задание с критериями оценки."""
    result = await get_ai().draft_task(
        need_title=payload.need_title, stack=payload.stack, grade=payload.grade
    )
    return AIResultOut(**result.as_dict())


@router.post(
    "/semantic/scores",
    response_model=AIResultOut,
    summary="Семантическое сопоставление потребности с профилями",
)
async def semantic_scores(payload: SemanticScoresIn, user: User = Depends(any_user)) -> AIResultOut:
    """Считает косинусную близость: с локальными эмбеддингами — семантическую."""
    result = await get_ai().semantic_scores(payload.need_text, payload.candidate_texts)
    return AIResultOut(**result.as_dict())


# --- Подсказки по накопленным сигналам ----------------------------------------
#
# Надстройка над подбором, а не замена: веса рубрики и присвоение грейда тестом
# не затрагиваются. Считается по данным платформы, модель — только для семантики.


@router.get(
    "/candidate/vacancy-hints",
    summary="Вакансии, близкие к вашим интересам и категории",
)
async def candidate_vacancy_hints(
    limit: int = 5,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Подсказывает вакансии: сначала по вашим откликам, иначе по профилю и категории."""
    return await suggestion.vacancy_hints(session, user.id, limit=max(1, min(limit, 20)))


@router.get(
    "/employer/candidate-hints",
    summary="Кандидаты, близкие к вашим действиям",
)
async def employer_candidate_hints(
    limit: int = 5,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Подсказывает кандидатов по вашим потребностям и приглашениям, кроме уже приглашённых."""
    return await suggestion.candidate_hints(session, user.id, limit=max(1, min(limit, 20)))
