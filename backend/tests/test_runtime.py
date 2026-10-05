"""Тесты запуска и инфраструктуры: логирование, жизненный цикл приложения, сессии БД.

Проверяется поведение, от которого зависит работоспособность стенда: сервис
поднимается даже при недоступной БД, а readiness честно об этом сообщает.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.db.session as db_session
import app.main as main
from app.core.logging import setup_logging


@pytest.fixture(autouse=True)
def _restore_engine_state():
    """Движок — глобальное состояние модуля: возвращаем его в исходный вид."""
    engine, factory = db_session._engine, db_session._session_factory
    yield
    db_session._engine, db_session._session_factory = engine, factory


# --- логирование -------------------------------------------------------------


def test_setup_logging_configures_stdout_handler():
    root = logging.getLogger()
    before = list(root.handlers)
    root.handlers.clear()
    try:
        setup_logging(debug=False)
        assert len(root.handlers) == 1
        assert root.level == logging.INFO
        assert isinstance(root.handlers[0], logging.StreamHandler)
    finally:
        root.handlers.clear()
        root.handlers.extend(before)


def test_setup_logging_debug_level_and_no_duplicate_handlers():
    root = logging.getLogger()
    before = list(root.handlers)
    root.handlers.clear()
    try:
        setup_logging(debug=True)
        setup_logging(debug=True)
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1, "повторный вызов не должен добавлять обработчик"
    finally:
        root.handlers.clear()
        root.handlers.extend(before)


# --- жизненный цикл приложения ----------------------------------------------


async def test_lifespan_prepares_reference_data_and_disposes_engine(db_factory, monkeypatch):
    """Штатный старт: справочники готовы, пул соединений закрывается на выходе."""
    disposed: list[bool] = []
    monkeypatch.setattr(main, "get_session_factory", lambda: db_factory)

    async def fake_dispose() -> None:
        disposed.append(True)

    monkeypatch.setattr(main, "dispose_engine", fake_dispose)

    async with main.lifespan(main.app), db_factory() as session:
        from sqlalchemy import select

        from app.models.testing import Specialization

        codes = (await session.execute(select(Specialization.code))).scalars().all()
        assert "backend" in codes, "справочники должны быть заполнены на старте"

    assert disposed == [True]


async def test_lifespan_survives_unavailable_database(monkeypatch, caplog):
    """Недоступная БД не должна валить сервис: ошибка логируется, приложение стартует."""

    def boom():
        raise RuntimeError("база недоступна")

    async def fake_dispose() -> None:
        return None

    monkeypatch.setattr(main, "get_session_factory", boom)
    monkeypatch.setattr(main, "dispose_engine", fake_dispose)

    with caplog.at_level(logging.WARNING, logger="app.main"):
        async with main.lifespan(main.app):
            pass

    assert "справочные данные не инициализированы" in caplog.text


async def test_root_endpoint_lists_service_points(client):
    """Служебная страница описывает сервис и не требует авторизации."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["docs"] == "/docs"
    assert body["openapi"].endswith("/openapi.json")


# --- сессии БД ---------------------------------------------------------------


def test_engine_and_factory_are_created_once(monkeypatch):
    created: list[object] = []

    class _FakeEngine:
        async def dispose(self) -> None:
            created.append("disposed")

    def fake_create(url, **kwargs):
        created.append(url)
        return _FakeEngine()

    db_session._engine = None
    db_session._session_factory = None
    monkeypatch.setattr(db_session, "create_async_engine", fake_create)

    first = db_session.get_engine()
    assert db_session.get_engine() is first, "движок создаётся один раз"
    assert len(created) == 1

    factory = db_session.get_session_factory()
    assert isinstance(factory, async_sessionmaker)
    assert db_session.get_session_factory() is factory


async def test_dispose_engine_resets_global_state(monkeypatch):
    disposed: list[bool] = []

    class _FakeEngine:
        async def dispose(self) -> None:
            disposed.append(True)

    db_session._engine = _FakeEngine()  # type: ignore[assignment]
    db_session._session_factory = "заглушка"  # type: ignore[assignment]

    await db_session.dispose_engine()

    assert disposed == [True]
    assert db_session._engine is None
    assert db_session._session_factory is None


async def test_dispose_engine_is_safe_without_engine():
    db_session._engine = None
    db_session._session_factory = None
    await db_session.dispose_engine()  # не должно падать


async def test_ping_database_reports_failure_instead_of_raising(monkeypatch, caplog):
    """Readiness-проба обязана возвращать False, а не падать."""

    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("нет соединения")

    monkeypatch.setattr(db_session, "get_engine", lambda: _BrokenEngine())

    with caplog.at_level(logging.WARNING, logger="app.db.session"):
        assert await db_session.ping_database() is False
    assert "database ping failed" in caplog.text
