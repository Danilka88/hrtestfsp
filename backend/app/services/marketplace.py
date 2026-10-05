"""Логика дополнительного функционала: вакансии, отклики, регулярные задания."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models.candidate import CandidateProfile
from app.models.employer import EmployerProfile
from app.models.marketplace import (
    APPLICATION_ACCEPTED,
    APPLICATION_DECLINED,
    APPLICATION_SENT,
    APPLICATION_VIEWED,
    SUBMISSION_NEW,
    SUBMISSION_REVIEWED,
    TASK_OPEN,
    VACANCY_CLOSED,
    VACANCY_PUBLISHED,
    Application,
    RegularTask,
    TaskSubmission,
    Vacancy,
)
from app.models.testing import SESSION_COMPLETED, Specialization, TestSession
from app.services.testing import GRADE_ORDER

logger = logging.getLogger(__name__)


class MarketplaceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def _specialization_id(session: AsyncSession, code: str | None) -> int | None:
    if not code:
        return None
    specialization = (
        await session.execute(select(Specialization).where(Specialization.code == code))
    ).scalar_one_or_none()
    if specialization is None:
        raise MarketplaceError(404, "Специализация не найдена")
    return specialization.id


def _validate_salary(salary_from: int, salary_to: int) -> None:
    if salary_from > salary_to:
        raise MarketplaceError(400, "Нижняя граница зарплаты больше верхней")


def _validate_grade(grade: str | None) -> None:
    if grade and grade not in GRADE_ORDER:
        raise MarketplaceError(400, "Неизвестный грейд")


async def _specialization_code(session: AsyncSession, specialization_id: int | None) -> str | None:
    if specialization_id is None:
        return None
    specialization = await session.get(Specialization, specialization_id)
    return specialization.code if specialization else None


# --- Вакансии -----------------------------------------------------------------


async def create_vacancy(session: AsyncSession, employer_id: str, payload: dict[str, Any]) -> Vacancy:
    _validate_salary(payload["salary_from"], payload["salary_to"])
    _validate_grade(payload.get("grade"))
    specialization_id = await _specialization_id(session, payload.get("specialization_code"))

    vacancy = Vacancy(
        employer_id=employer_id,
        title=payload["title"],
        description=payload.get("description"),
        specialization_id=specialization_id,
        grade_code=payload.get("grade"),
        stack=list(payload.get("stack") or []),
        salary_from=payload["salary_from"],
        salary_to=payload["salary_to"],
        status=VACANCY_PUBLISHED,
    )
    session.add(vacancy)
    await session.commit()
    await session.refresh(vacancy)
    return vacancy


async def vacancy_view(session: AsyncSession, vacancy: Vacancy) -> dict[str, Any]:
    company = (
        await session.execute(select(EmployerProfile).where(EmployerProfile.user_id == vacancy.employer_id))
    ).scalar_one_or_none()
    return {
        "id": vacancy.id,
        "title": vacancy.title,
        "description": vacancy.description,
        "specialization_code": await _specialization_code(session, vacancy.specialization_id),
        "grade": vacancy.grade_code,
        "stack": list(vacancy.stack or []),
        "salary_from": vacancy.salary_from,
        "salary_to": vacancy.salary_to,
        "status": vacancy.status,
        "company_name": company.company_name if company else None,
        "created_at": vacancy.created_at,
    }


async def list_vacancies(session: AsyncSession, employer_id: str) -> list[Vacancy]:
    return list(
        (
            await session.execute(
                select(Vacancy).where(Vacancy.employer_id == employer_id).order_by(Vacancy.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_open_vacancies(
    session: AsyncSession, *, specialization_code: str | None = None, limit: int = 50
) -> list[Vacancy]:
    query = select(Vacancy).where(Vacancy.status == VACANCY_PUBLISHED)
    if specialization_code:
        specialization_id = await _specialization_id(session, specialization_code)
        query = query.where(Vacancy.specialization_id == specialization_id)
    query = query.order_by(Vacancy.created_at.desc()).limit(limit)
    return list((await session.execute(query)).scalars().all())


async def close_vacancy(session: AsyncSession, employer_id: str, vacancy_id: str) -> Vacancy:
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.employer_id != employer_id:
        raise MarketplaceError(404, "Вакансия не найдена")
    vacancy.status = VACANCY_CLOSED
    vacancy.closed_at = utcnow()
    await session.commit()
    await session.refresh(vacancy)
    return vacancy


# --- Отклики ------------------------------------------------------------------


async def apply_to_vacancy(
    session: AsyncSession, candidate_user_id: str, *, vacancy_id: str, message: str | None
) -> Application:
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise MarketplaceError(404, "Вакансия не найдена")
    if vacancy.status != VACANCY_PUBLISHED:
        raise MarketplaceError(409, "Вакансия закрыта")

    existing = (
        await session.execute(
            select(Application).where(
                Application.vacancy_id == vacancy_id,
                Application.candidate_user_id == candidate_user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise MarketplaceError(409, "Отклик на эту вакансию уже отправлен")

    application = Application(
        vacancy_id=vacancy_id,
        candidate_user_id=candidate_user_id,
        message=message,
        status=APPLICATION_SENT,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


async def application_candidate_view(session: AsyncSession, application: Application) -> dict[str, Any]:
    vacancy = await session.get(Vacancy, application.vacancy_id)
    company = None
    if vacancy is not None:
        profile = (
            await session.execute(
                select(EmployerProfile).where(EmployerProfile.user_id == vacancy.employer_id)
            )
        ).scalar_one_or_none()
        company = profile.company_name if profile else None
    return {
        "id": application.id,
        "vacancy_id": application.vacancy_id,
        "vacancy_title": vacancy.title if vacancy else None,
        "company_name": company,
        "message": application.message,
        "status": application.status,
        "created_at": application.created_at,
        "viewed_at": application.viewed_at,
        "decided_at": application.decided_at,
    }


async def application_employer_view(session: AsyncSession, application: Application) -> dict[str, Any]:
    """Работодатель видит контакты откликнувшегося: кандидат проявил инициативу сам."""
    profile = (
        await session.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == application.candidate_user_id)
        )
    ).scalar_one_or_none()
    contacts = None
    if profile is not None:
        raw = profile.contacts or {}
        contacts = {"email": raw.get("email"), "phone": raw.get("phone"), "telegram": raw.get("telegram")}
    return {
        "id": application.id,
        "vacancy_id": application.vacancy_id,
        "candidate_reference": f"cand-{application.candidate_user_id[:8]}",
        "candidate_name": profile.full_name if profile else None,
        "candidate_specialization": profile.specialization if profile else None,
        "candidate_grade": profile.grade if profile else None,
        "candidate_stack": list((profile.stack or []) if profile else []),
        "message": application.message,
        "status": application.status,
        "created_at": application.created_at,
        "viewed_at": application.viewed_at,
        "decided_at": application.decided_at,
        "candidate_contacts": contacts,
        "contacts_revealed": True,
    }


async def list_candidate_applications(session: AsyncSession, candidate_user_id: str) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.execute(
                select(Application)
                .where(Application.candidate_user_id == candidate_user_id)
                .order_by(Application.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await application_candidate_view(session, row) for row in rows]


async def list_vacancy_applications(
    session: AsyncSession, employer_id: str, vacancy_id: str
) -> list[dict[str, Any]]:
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.employer_id != employer_id:
        raise MarketplaceError(404, "Вакансия не найдена")
    rows = list(
        (
            await session.execute(
                select(Application)
                .where(Application.vacancy_id == vacancy_id)
                .order_by(Application.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await application_employer_view(session, row) for row in rows]


async def decide_application(
    session: AsyncSession, employer_id: str, application_id: str, *, accept: bool
) -> Application:
    application = await session.get(Application, application_id)
    if application is None:
        raise MarketplaceError(404, "Отклик не найден")
    vacancy = await session.get(Vacancy, application.vacancy_id)
    if vacancy is None or vacancy.employer_id != employer_id:
        raise MarketplaceError(404, "Отклик не найден")
    if application.status in (APPLICATION_ACCEPTED, APPLICATION_DECLINED):
        raise MarketplaceError(409, "Решение по отклику уже принято")

    application.status = APPLICATION_ACCEPTED if accept else APPLICATION_DECLINED
    application.decided_at = utcnow()
    if application.viewed_at is None:
        application.viewed_at = application.decided_at
    await session.commit()
    await session.refresh(application)
    return application


# --- Регулярные короткие задания ----------------------------------------------


async def create_task(session: AsyncSession, employer_id: str, payload: dict[str, Any]) -> RegularTask:
    _validate_grade(payload.get("grade"))
    specialization_id = await _specialization_id(session, payload.get("specialization_code"))
    task = RegularTask(
        employer_id=employer_id,
        title=payload["title"],
        description=payload.get("description"),
        specialization_id=specialization_id,
        grade_code=payload.get("grade"),
        status=TASK_OPEN,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def task_view(session: AsyncSession, task: RegularTask) -> dict[str, Any]:
    company = (
        await session.execute(select(EmployerProfile).where(EmployerProfile.user_id == task.employer_id))
    ).scalar_one_or_none()
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "specialization_code": await _specialization_code(session, task.specialization_id),
        "grade": task.grade_code,
        "status": task.status,
        "company_name": company.company_name if company else None,
        "created_at": task.created_at,
    }


async def list_open_tasks(
    session: AsyncSession, candidate_user_id: str, *, limit: int = 20
) -> list[RegularTask]:
    """Задания, релевантные специализации кандидата (или общие)."""
    profile = (
        await session.execute(select(CandidateProfile).where(CandidateProfile.user_id == candidate_user_id))
    ).scalar_one_or_none()

    query = select(RegularTask).where(RegularTask.status == TASK_OPEN)
    tasks = list(
        (await session.execute(query.order_by(RegularTask.created_at.desc()).limit(limit))).scalars().all()
    )
    if profile is not None and profile.specialization:
        preferred = [
            t
            for t in tasks
            if t.specialization_id is None
            or (
                t.specialization_id
                and await _specialization_code(session, t.specialization_id) == profile.specialization
            )
        ]
        return preferred
    return tasks


async def submit_solution(
    session: AsyncSession, candidate_user_id: str, *, task_id: str, solution: str
) -> TaskSubmission:
    task = await session.get(RegularTask, task_id)
    if task is None or task.status != TASK_OPEN:
        raise MarketplaceError(404, "Задание недоступно")
    if not solution.strip():
        raise MarketplaceError(400, "Решение не может быть пустым")

    submission = TaskSubmission(
        task_id=task_id,
        candidate_user_id=candidate_user_id,
        solution=solution.strip(),
        status=SUBMISSION_NEW,
    )
    session.add(submission)
    await session.commit()
    await session.refresh(submission)
    return submission


async def list_submissions(
    session: AsyncSession, employer_id: str, task_id: str
) -> list[tuple[TaskSubmission, CandidateProfile | None]]:
    task = await session.get(RegularTask, task_id)
    if task is None or task.employer_id != employer_id:
        raise MarketplaceError(404, "Задание не найдено")

    rows = list(
        (
            await session.execute(
                select(TaskSubmission)
                .where(TaskSubmission.task_id == task_id)
                .order_by(TaskSubmission.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    result: list[tuple[TaskSubmission, CandidateProfile | None]] = []
    for row in rows:
        profile = (
            await session.execute(
                select(CandidateProfile).where(CandidateProfile.user_id == row.candidate_user_id)
            )
        ).scalar_one_or_none()
        result.append((row, profile))
    return result


async def list_employer_tasks(session: AsyncSession, employer_id: str) -> list[RegularTask]:
    return list(
        (
            await session.execute(
                select(RegularTask)
                .where(RegularTask.employer_id == employer_id)
                .order_by(RegularTask.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def last_activity_at(session: AsyncSession, user_id: str) -> datetime | None:
    """Свежесть профиля: последний завершённый тест или участие в регулярном задании."""
    finished = await session.scalar(
        select(TestSession.finished_at)
        .where(TestSession.user_id == user_id, TestSession.status == SESSION_COMPLETED)
        .order_by(TestSession.finished_at.desc())
        .limit(1)
    )
    submitted = await session.scalar(
        select(TaskSubmission.created_at)
        .where(TaskSubmission.candidate_user_id == user_id)
        .order_by(TaskSubmission.created_at.desc())
        .limit(1)
    )
    candidates = [moment for moment in (finished, submitted) if moment is not None]
    return max(candidates) if candidates else None


__all__ = [
    "MarketplaceError",
    "create_vacancy",
    "vacancy_view",
    "list_vacancies",
    "list_open_vacancies",
    "close_vacancy",
    "apply_to_vacancy",
    "list_candidate_applications",
    "list_vacancy_applications",
    "decide_application",
    "create_task",
    "task_view",
    "list_open_tasks",
    "list_employer_tasks",
    "submit_solution",
    "list_submissions",
    "last_activity_at",
    "SUBMISSION_REVIEWED",
    "APPLICATION_VIEWED",
]
