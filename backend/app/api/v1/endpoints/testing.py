"""Эндпоинты тестирования и категоризации (кабинет кандидата)."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.testing import Grade, Specialization
from app.models.user import User, UserRole
from app.schemas.testing import (
    AnswerRequest,
    AnswerResponse,
    CategoryStatusOut,
    GradeOut,
    ItemOut,
    SessionResultOut,
    SpecializationOut,
    StartSessionRequest,
    StartSessionResponse,
    SurveyRequest,
    SurveyResponseOut,
)
from app.services import testing_flow
from app.services.testing_flow import TestingError

router = APIRouter(prefix="/testing", tags=["testing"])

candidate_only = require_roles(UserRole.CANDIDATE)


def _raise(exc: TestingError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/specializations", response_model=list[SpecializationOut], summary="Справочник специализаций")
async def list_specializations(session: AsyncSession = Depends(get_session)) -> list[Specialization]:
    result = await session.execute(
        select(Specialization).where(Specialization.is_active.is_(True)).order_by(Specialization.id)
    )
    return list(result.scalars().all())


@router.get("/grades", response_model=list[GradeOut], summary="Справочник грейдов")
async def list_grades(session: AsyncSession = Depends(get_session)) -> list[Grade]:
    result = await session.execute(select(Grade).order_by(Grade.rank_order))
    return list(result.scalars().all())


@router.post("/survey", response_model=SurveyResponseOut, summary="Опрос по отрасли и специализации")
async def submit_survey(
    payload: SurveyRequest,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> SurveyResponseOut:
    try:
        record, options = await testing_flow.save_survey(
            session,
            user.id,
            industry=payload.industry,
            specialization_code=payload.specialization_code,
            answers=payload.answers,
        )
    except TestingError as exc:
        _raise(exc)
    return SurveyResponseOut(
        id=record.id,
        industry=record.industry,
        specialization_code=payload.specialization_code,
        grade_options=options,
        created_at=record.created_at,
    )


@router.post("/sessions", response_model=StartSessionResponse, summary="Начать тест на заявленный грейд")
async def start_session(
    payload: StartSessionRequest,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> StartSessionResponse:
    try:
        test_session, item = await testing_flow.start_session(
            session,
            user.id,
            specialization_code=payload.specialization_code,
            target_grade=payload.target_grade,
        )
    except TestingError as exc:
        _raise(exc)
    return StartSessionResponse(
        session_id=test_session.id,
        target_grade=test_session.target_grade,
        item=ItemOut.model_validate(item),
        note="Отвечайте последовательно: следующее задание подбирается по текущей оценке.",
    )


@router.post(
    "/sessions/{session_id}/answers",
    response_model=AnswerResponse,
    summary="Ответить на задание (адаптивная выдача следующего)",
)
async def answer(
    session_id: str,
    payload: AnswerRequest,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> AnswerResponse:
    try:
        outcome = await testing_flow.submit_answer(
            session,
            user.id,
            session_id=session_id,
            item_id=payload.item_id,
            answer_index=payload.answer_index,
            response_time_ms=payload.response_time_ms,
        )
    except TestingError as exc:
        _raise(exc)

    return AnswerResponse(
        correct=outcome.correct,
        finished=outcome.finished,
        next_item=ItemOut.model_validate(outcome.next_item) if outcome.next_item else None,
        result=SessionResultOut.model_validate(outcome.result) if outcome.result else None,
    )


@router.get(
    "/me/category",
    response_model=CategoryStatusOut,
    summary="Текущая категория, история тестов и ограничение смены грейда",
)
async def my_category(
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> CategoryStatusOut:
    status = await testing_flow.current_category(session, user.id)
    return CategoryStatusOut.model_validate(status)
