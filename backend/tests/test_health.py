"""Проверки живости, готовности и контракта OpenAPI."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"]
    assert payload["version"]


def test_ready_reports_database_state() -> None:
    """Readiness не падает при недоступной БД — сообщает состояние."""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["database"] in {"ok", "unavailable"}
    assert set(payload["providers"]) == {"llm", "fsp", "email", "storage"}


def test_root_meta() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


def test_openapi_available() -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"]
    assert "/api/v1/health" in spec["paths"]
