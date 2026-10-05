"""Асинхронная сессия БД.

Важно: движок создаётся лениво. Приложение стартует и отвечает на /health даже
если БД недоступна — недоступность отражается в /health/ready, а не падением.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Ленивая инициализация движка."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(bind=get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _session_factory


async def get_session():
    """FastAPI-зависимость: выдаёт асинхронную сессию."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def ping_database() -> bool:
    """Проверка доступности БД для readiness-пробы."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — readiness не должен падать
        logger.warning("database ping failed: %s", exc)
        return False


async def dispose_engine() -> None:
    """Корректное закрытие пула соединений при остановке приложения."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
