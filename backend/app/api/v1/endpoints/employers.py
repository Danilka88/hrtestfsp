"""Эндпоинты кабинета работодателя: компания, потребность, подборка, поиск."""

from __future__ import annotations

from typing import List, NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.user import User, UserRole
from app.schemas.employer import (
    CandidateCardOut,
    EmployerProfileIn,
    EmployerProfileOut,
    NeedIn,
    SearchQuery,
    SearchResultOut,
    SelectionOut,
    SelectionSummaryOut,
)
from app.services import employers as employer_service
from app.services.employers import EmployerError

router = APIRouter(prefix="/employers/me", tags=["employers"])

employer_only = require_roles(UserRole.EMPLOYER)


def _raise(exc: EmployerError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/profile", response_model=EmployerProfileOut, summary="Профиль компании")
async def get_profile(
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> EmployerProfileOut:
    profile = await employer_service.get_profile(session, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Профиль компании ещё не создан")
    return EmployerProfileOut.model_validate(profile)


@router.put("/profile", response_model=EmployerProfileOut, summary="Заполнить профиль компании")
async def put_profile(
    payload: EmployerProfileIn,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> EmployerProfileOut:
    profile = await employer_service.upsert_profile(session, user.id, payload)
    return EmployerProfileOut.model_validate(profile)


@router.post(
    "/needs",
    response_model=SelectionOut,
    summary="Описать потребность и получить подборку кандидатов",
)
async def create_need(
    payload: NeedIn,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> SelectionOut:
    try:
        need = await employer_service.create_need(session, user.id, payload)
        selection, _ = await employer_service.build_selection(session, user.id, need)
    except EmployerError as exc:
        _raise(exc)
    return await _selection_response(session, user.id, selection.id)


@router.get("/selections", response_model=List[SelectionSummaryOut], summary="Список подборок")
async def list_selections(
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> List[SelectionSummaryOut]:
    rows = await employer_service.list_selections(session, user.id)
    return [
        SelectionSummaryOut(
            id=selection.id, title=selection.title,
            parent_selection_id=selection.parent_selection_id,
            candidates_count=count, created_at=selection.created_at,
        )
        for selection, count in rows
    ]


@router.get("/selections/{selection_id}", response_model=SelectionOut, summary="Подборка с объяснениями")
async def get_selection(
    selection_id: str,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> SelectionOut:
    return await _selection_response(session, user.id, selection_id)


@router.post(
    "/selections/{selection_id}/refine",
    response_model=SelectionOut,
    summary="Уточнить запрос — создаётся новая подборка, прежняя сохраняется",
)
async def refine_selection(
    selection_id: str,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
    stack: Optional[List[str]] = Query(default=None, description="Уточнённый стек"),
    grade: Optional[str] = Query(default=None, description="Уточнённый грейд"),
) -> SelectionOut:
    try:
        previous, _ = await employer_service.get_selection(session, user.id, selection_id)
        need = await session.get(
            employer_service.EmployerNeed, previous.need_id
        ) if previous.need_id else None
        if need is None:
            raise EmployerError(409, "У прежней подборки нет сохранённой потребности")
        selection, _ = await employer_service.build_selection(
            session, user.id, need,
            parent_selection_id=previous.id,
            stack_override=stack if stack is not None else None,
            grade_override=grade,
            title=f"{previous.title} (уточнение)",
        )
    except EmployerError as exc:
        _raise(exc)
    return await _selection_response(session, user.id, selection.id)


@router.get("/search", response_model=SearchResultOut, summary="Поиск по банку кандидатов")
async def search(
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
    specialization_code: Optional[str] = Query(default=None),
    grade: Optional[str] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    stack: Optional[List[str]] = Query(default=None),
    has_fsp: Optional[bool] = Query(default=None, description="Только с подтверждёнными достижениями"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchResultOut:
    query = SearchQuery(
        specialization_code=specialization_code, grade=grade, category_id=category_id,
        stack=stack or [], has_fsp=has_fsp, limit=limit, offset=offset,
    )
    total, candidates = await employer_service.search_candidates(session, query)
    return SearchResultOut(
        total=total, limit=limit, offset=offset,
        candidates=[CandidateCardOut.model_validate(c) for c in candidates],
    )


async def _selection_response(
    session: AsyncSession, employer_id: str, selection_id: str
) -> SelectionOut:
    selection, rows = await employer_service.get_selection(session, employer_id, selection_id)
    cards = [
        CandidateCardOut.model_validate(
            employer_service.selection_candidate_card(record, profile, candidate_user)
        )
        for record, profile, candidate_user in rows
    ]
    return SelectionOut(
        id=selection.id,
        title=selection.title,
        need_id=selection.need_id,
        parent_selection_id=selection.parent_selection_id,
        rubric_version=selection.rubric_version,
        params=selection.params or {},
        recommended_categories=list((selection.params or {}).get("recommended_categories", [])),
        candidates=cards,
        created_at=selection.created_at,
    )
