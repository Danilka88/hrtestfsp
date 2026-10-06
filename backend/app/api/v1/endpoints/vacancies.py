"""Эндпоинты вакансий и откликов (дополнительный функционал)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.marketplace import APPLICATION_ACCEPTED, APPLICATION_DECLINED
from app.models.user import User, UserRole
from app.schemas.marketplace import (
    ApplicationCandidateOut,
    ApplicationDecision,
    ApplicationEmployerOut,
    ApplicationIn,
    VacancyIn,
    VacancyOut,
)
from app.services import marketplace as market
from app.services.marketplace import MarketplaceError

router_employer = APIRouter(prefix="/employers/me/vacancies", tags=["vacancies:employer"])
router_candidate = APIRouter(prefix="/candidates/me", tags=["vacancies:candidate"])

employer_only = require_roles(UserRole.EMPLOYER)
candidate_only = require_roles(UserRole.CANDIDATE)


@router_employer.post("", response_model=VacancyOut, summary="Опубликовать вакансию")
async def publish_vacancy(
    payload: VacancyIn,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> VacancyOut:
    vacancy = await market.create_vacancy(session, user.id, payload.model_dump())
    return VacancyOut.model_validate(await market.vacancy_view(session, vacancy))


@router_employer.get("", response_model=list[VacancyOut], summary="Вакансии работодателя")
async def my_vacancies(
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> list[VacancyOut]:
    vacancies = await market.list_vacancies(session, user.id)
    return [VacancyOut.model_validate(await market.vacancy_view(session, v)) for v in vacancies]


@router_employer.put("/{vacancy_id}", response_model=VacancyOut, summary="Изменить опубликованную вакансию")
async def update_vacancy(
    vacancy_id: str,
    payload: VacancyIn,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> VacancyOut:
    vacancy = await market.update_vacancy(session, user.id, vacancy_id, payload.model_dump())
    return VacancyOut.model_validate(await market.vacancy_view(session, vacancy))


@router_employer.post("/{vacancy_id}/close", response_model=VacancyOut, summary="Закрыть вакансию")
async def close_vacancy(
    vacancy_id: str,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> VacancyOut:
    vacancy = await market.close_vacancy(session, user.id, vacancy_id)
    return VacancyOut.model_validate(await market.vacancy_view(session, vacancy))


@router_employer.get(
    "/{vacancy_id}/applications",
    response_model=list[ApplicationEmployerOut],
    summary="Отклики на вакансию (контакты раскрыты — кандидат откликнулся сам)",
)
async def vacancy_applications(
    vacancy_id: str,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationEmployerOut]:
    views = await market.list_vacancy_applications(session, user.id, vacancy_id)
    return [ApplicationEmployerOut.model_validate(v) for v in views]


@router_employer.post(
    "/applications/{application_id}/decision",
    response_model=ApplicationEmployerOut,
    summary="Принять или отклонить отклик",
)
async def decide_application(
    application_id: str,
    payload: ApplicationDecision,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> ApplicationEmployerOut:
    if payload.status not in {APPLICATION_ACCEPTED, APPLICATION_DECLINED}:
        raise MarketplaceError(400, "Допустимые значения: accepted или declined")
    application = await market.decide_application(
        session, user.id, application_id, accept=payload.status == "accepted"
    )
    return ApplicationEmployerOut.model_validate(await market.application_employer_view(session, application))


@router_candidate.get("/vacancies", response_model=list[VacancyOut], summary="Открытые вакансии")
async def open_vacancies(
    specialization_code: str | None = Query(default=None),
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> list[VacancyOut]:
    vacancies = await market.list_open_vacancies(session, specialization_code=specialization_code)
    return [VacancyOut.model_validate(await market.vacancy_view(session, v)) for v in vacancies]


@router_candidate.post(
    "/vacancies/{vacancy_id}/applications",
    response_model=ApplicationCandidateOut,
    summary="Откликнуться на вакансию",
)
async def apply(
    vacancy_id: str,
    payload: ApplicationIn,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> ApplicationCandidateOut:
    application = await market.apply_to_vacancy(
        session, user.id, vacancy_id=vacancy_id, message=payload.message
    )
    return ApplicationCandidateOut.model_validate(
        await market.application_candidate_view(session, application)
    )


@router_candidate.get(
    "/applications", response_model=list[ApplicationCandidateOut], summary="Мои отклики и их статусы"
)
async def my_applications(
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationCandidateOut]:
    views = await market.list_candidate_applications(session, user.id)
    return [ApplicationCandidateOut.model_validate(v) for v in views]
