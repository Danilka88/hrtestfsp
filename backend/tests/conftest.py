"""Общие фикстуры тестов.

Тесты работают на SQLite в памяти с переопределением зависимости `get_session`,
поэтому не требуют запущенного PostgreSQL.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

# Тесты не должны зависеть от локальной LLM: результат был бы недетерминированным
# и медленным. Принудительно включаем демо-режим до создания настроек.
os.environ["LLM_PROVIDER"] = "mock"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  — регистрирует модели в Base.metadata
from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.providers.registry import reset_llm_provider  # noqa: E402
from app.services.reference import ensure_reference_data  # noqa: E402

TEST_DATABASE_URL = "sqlite+aiosqlite://"

# Фабрика сессий текущего теста — нужна тестам, которым требуется доступ к БД
# напрямую (например, чтобы узнать правильные ответы банка заданий).
_current_factory = None


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    global _current_factory
    reset_llm_provider()  # провайдер LLM пересобирается под демо-режим тестов
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    _current_factory = session_factory

    # Справочники и банк заданий нужны для тестов тестирования
    async with session_factory() as seed_session:
        await ensure_reference_data(seed_session)

    async def override_get_session() -> AsyncIterator:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def db_factory(client: AsyncClient):
    """Фабрика сессий БД (зависит от `client` — движок уже создан и наполнен)."""
    return _current_factory


async def register_and_verify(
    client: AsyncClient, email: str, password: str = "secret12345", role: str = "candidate"
) -> dict:
    """Хелпер: полный путь регистрации с подтверждением email."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "role": role, "consent_pdn": True},
    )
    assert response.status_code == 201, response.text
    token = response.json()["verification_token"]
    verify = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify.status_code == 200, verify.text
    return verify.json()
