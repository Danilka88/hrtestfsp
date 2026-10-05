"""Эндпоинты регулярных коротких заданий (дополнительный функционал)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.user import User, UserRole
from app.schemas.marketplace import SubmissionIn, SubmissionOut, TaskIn, TaskOut
from app.services import marketplace as market

router_employer = APIRouter(prefix="/employers/me/tasks", tags=["tasks:employer"])
router_candidate = APIRouter(prefix="/candidates/me/tasks", tags=["tasks:candidate"])

employer_only = require_roles(UserRole.EMPLOYER)
candidate_only = require_roles(UserRole.CANDIDATE)


@router_employer.post("", response_model=TaskOut, summary="Создать короткое задание")
async def create_task(
    payload: TaskIn,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> TaskOut:
    task = await market.create_task(session, user.id, payload.model_dump())
    return TaskOut.model_validate(await market.task_view(session, task))


@router_employer.get("", response_model=list[TaskOut], summary="Задания работодателя")
async def my_tasks(
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> list[TaskOut]:
    tasks = await market.list_employer_tasks(session, user.id)
    return [TaskOut.model_validate(await market.task_view(session, t)) for t in tasks]


@router_employer.get(
    "/{task_id}/submissions",
    response_model=list[SubmissionOut],
    summary="Решения кандидатов по заданию",
)
async def task_submissions(
    task_id: str,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> list[SubmissionOut]:
    rows = await market.list_submissions(session, user.id, task_id)
    return [
        SubmissionOut(
            id=submission.id,
            task_id=submission.task_id,
            candidate_reference=f"cand-{submission.candidate_user_id[:8]}",
            candidate_name=profile.full_name if profile else None,
            candidate_specialization=profile.specialization if profile else None,
            candidate_grade=profile.grade if profile else None,
            solution=submission.solution,
            status=submission.status,
            created_at=submission.created_at,
        )
        for submission, profile in rows
    ]


@router_candidate.get("", response_model=list[TaskOut], summary="Предложенные короткие задания")
async def offered_tasks(
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> list[TaskOut]:
    tasks = await market.list_open_tasks(session, user.id)
    return [TaskOut.model_validate(await market.task_view(session, t)) for t in tasks]


@router_candidate.post(
    "/{task_id}/submissions",
    response_model=SubmissionOut,
    summary="Решить задание или предложить подход",
)
async def submit(
    task_id: str,
    payload: SubmissionIn,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> SubmissionOut:
    submission = await market.submit_solution(session, user.id, task_id=task_id, solution=payload.solution)
    return SubmissionOut(
        id=submission.id,
        task_id=submission.task_id,
        candidate_reference=f"cand-{submission.candidate_user_id[:8]}",
        solution=submission.solution,
        status=submission.status,
        created_at=submission.created_at,
    )
