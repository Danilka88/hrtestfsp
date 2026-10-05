"""Сборка маршрутов API v1.

По мере реализации этапов сюда добавляются роутеры модулей:
auth, candidates, employers, testing, matching, invitations, vacancies, tasks, fsp.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router)
