"""Кабинет администратора: наблюдение за платформой как за двусторонним рынком.

Все методы — только чтение и доступны исключительно роли `admin`. Регистрация в
качестве администратора невозможна (роль не входит в список самостоятельно
регистрируемых), учётная запись создаётся при загрузке демо-данных.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.user import User, UserRole
from app.schemas.ai import AIResultOut
from app.services import analytics
from app.services.ai import get_ai

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = require_roles(UserRole.ADMIN)


@router.get("/overview", summary="Ключевые показатели, воронка кандидата и ликвидность")
async def overview(
    user: User = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Сводка состояния платформы: обе стороны, путь кандидата, ликвидность рынка."""
    return await analytics.overview(session)


@router.get("/categories", summary="Спрос и предложение по категориям")
async def categories(
    user: User = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Где рынок сбалансирован, где дефицит кандидатов, а где нет спроса."""
    return await analytics.categories(session)


@router.get("/companies", summary="Активность работодателей")
async def companies(
    user: User = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Кто из компаний реально выходит на контакт, а кто только зарегистрировался."""
    return await analytics.companies(session)


@router.get("/interactions", summary="Схема взаимодействия компаний и кандидатов")
async def interactions(
    limit: int = Query(default=60, ge=5, le=300, description="Сколько последних связей показать"),
    user: User = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Узлы обеих сторон и связи-приглашения между ними — для схемы взаимодействия."""
    return await analytics.interactions(session, limit=limit)


@router.get("/anomalies", summary="Сигналы, требующие внимания")
async def anomalies(
    user: User = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Проверки по данным: пустые категории, зависшие приглашения, дубли компаний."""
    return await analytics.anomalies(session)


@router.post(
    "/ai/summary",
    response_model=AIResultOut,
    summary="Сводка состояния платформы человеческим языком",
)
async def ai_summary(
    user: User = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> AIResultOut:
    """Модель связывает уже посчитанные показатели; числа она не вычисляет."""
    metrics = await analytics.overview(session)
    result = await get_ai().platform_summary(metrics)
    return AIResultOut(**result.as_dict())


@router.post(
    "/ai/recommendations",
    response_model=AIResultOut,
    summary="Что сделать администратору по текущим показателям",
)
async def ai_recommendations(
    user: User = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> AIResultOut:
    """Конкретные действия по показателям: дефицит категорий, зависшие приглашения."""
    metrics = await analytics.overview(session)
    result = await get_ai().platform_recommendations(metrics)
    return AIResultOut(**result.as_dict())
