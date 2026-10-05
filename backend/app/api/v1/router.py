"""Сборка маршрутов API v1.

По мере реализации этапов сюда добавляются роутеры модулей:
candidates, employers, testing, matching, invitations, vacancies, tasks, fsp.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, candidates, employers, health, testing

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(candidates.router)
api_router.include_router(testing.router)
api_router.include_router(employers.router)
