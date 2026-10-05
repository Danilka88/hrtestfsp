"""Проверки работоспособности сервиса.

/health        — живость процесса (не зависит от БД и провайдеров)
/health/ready  — готовность: доступность БД и состояние провайдеров
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import ping_database
from app.providers.registry import get_providers

router = APIRouter(tags=["health"])


@router.get("/health", summary="Живость сервиса")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/health/ready", summary="Готовность сервиса и зависимостей")
async def ready() -> dict:
    db_ok = await ping_database()

    providers: dict[str, bool] = {}
    for name, provider in get_providers().items():
        try:
            providers[name] = await provider.health()
        except Exception:  # noqa: BLE001 — readiness не должен падать
            providers[name] = False

    overall = "ok" if db_ok and all(providers.values()) else "degraded"
    return {
        "status": overall,
        "database": "ok" if db_ok else "unavailable",
        "providers": providers,
    }
