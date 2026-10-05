"""Сборка маршрутов API v1.

По мере реализации этапов сюда добавляются роутеры модулей:
candidates, employers, testing, matching, invitations, vacancies, tasks, fsp.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    ai,
    auth,
    candidates,
    employers,
    fsp,
    health,
    invitations,
    tasks,
    testing,
    vacancies,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(candidates.router)
api_router.include_router(fsp.router)
api_router.include_router(testing.router)
api_router.include_router(ai.router)
api_router.include_router(employers.router)
api_router.include_router(invitations.router_employer)
api_router.include_router(invitations.router_candidate)
api_router.include_router(vacancies.router_employer)
api_router.include_router(vacancies.router_candidate)
api_router.include_router(tasks.router_employer)
api_router.include_router(tasks.router_candidate)
api_router.include_router(admin.router)
