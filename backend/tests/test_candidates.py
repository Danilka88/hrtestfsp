"""Тесты профиля кандидата: форма, PDF-резюме, генерация PDF, приватность."""

from __future__ import annotations

import io
from collections.abc import Sequence

import pytest
from httpx import AsyncClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services.profile_pdf import ensure_fonts, resolve_font_name
from tests.conftest import register_and_verify

RESUME_TEXT = """Иван Петров
ivan.petrov@example.com
+7 999 123-45-67

Backend-разработчик, senior
Опыт 6 лет

Стек: Python, FastAPI, PostgreSQL, Docker, Kubernetes, Redis, Kafka, Git

Командная работа, менторство, ответственность
"""


def _make_pdf(lines: Sequence[str]) -> bytes:
    """Собирает PDF с текстовым слоем (для проверки извлечения текста)."""
    ensure_fonts()
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont(resolve_font_name(), 12)
    y = 780
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 18
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


async def _token(client: AsyncClient, email: str, role: str = "candidate") -> str:
    await register_and_verify(client, email, role=role)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "secret12345"})
    return login.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_profile_404_before_creation(client: AsyncClient) -> None:
    token = await _token(client, "empty@example.com")
    response = await client.get("/api/v1/candidates/me/profile", headers=_auth(token))
    assert response.status_code == 404


async def test_put_profile_and_read_back(client: AsyncClient) -> None:
    token = await _token(client, "form@example.com")
    payload = {
        "full_name": "Мария Сидорова",
        "contacts": {"email": "maria@example.com", "telegram": "@maria"},
        "specialization": "backend",
        "grade": "middle",
        "experience_years": 4,
        "stack": ["Python", "Django", "PostgreSQL"],
        "roles": ["backend"],
        "soft_skills": ["командная работа"],
        "summary": "Разрабатываю сервисы на Python.",
    }
    created = await client.put("/api/v1/candidates/me/profile", json=payload, headers=_auth(token))
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["full_name"] == "Мария Сидорова"
    assert body["resume_source"] == "form"
    assert body["privacy"]["show_contacts"] is False  # контакты скрыты по умолчанию

    fetched = await client.get("/api/v1/candidates/me/profile", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["stack"] == ["Python", "Django", "PostgreSQL"]


async def test_profile_requires_candidate_role(client: AsyncClient) -> None:
    token = await _token(client, "employer-profile@example.com", role="employer")
    response = await client.get("/api/v1/candidates/me/profile", headers=_auth(token))
    assert response.status_code == 403


async def test_profile_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/candidates/me/profile")).status_code == 401


async def test_upload_resume_parses_fields(client: AsyncClient) -> None:
    token = await _token(client, "resume@example.com")
    files = {"file": ("resume.pdf", _make_pdf(RESUME_TEXT.split("\n")), "application/pdf")}
    response = await client.post("/api/v1/candidates/me/resume", files=files, headers=_auth(token))
    assert response.status_code == 200, response.text

    body = response.json()
    parsed = body["parsed"]
    assert parsed["contacts"]["email"] == "ivan.petrov@example.com"
    assert "Python" in parsed["stack"]
    assert "PostgreSQL" in parsed["stack"]
    assert parsed["grade"] == "senior"
    assert parsed["experience_years"] == 6
    assert body["profile"]["resume_source"] == "pdf_upload"
    assert body["text_chars"] > 0


async def test_upload_rejects_non_pdf(client: AsyncClient) -> None:
    token = await _token(client, "notpdf@example.com")
    files = {"file": ("resume.txt", b"just text", "text/plain")}
    response = await client.post("/api/v1/candidates/me/resume", files=files, headers=_auth(token))
    assert response.status_code == 415


async def test_upload_rejects_pdf_without_text_layer(client: AsyncClient) -> None:
    """Скан без текстового слоя не подменяется пустым результатом."""
    token = await _token(client, "scan@example.com")
    blank = _make_pdf([])  # страница без текста
    files = {"file": ("scan.pdf", blank, "application/pdf")}
    response = await client.post("/api/v1/candidates/me/resume", files=files, headers=_auth(token))
    assert response.status_code == 400
    assert "текстовый слой" in response.json()["detail"]


async def test_privacy_can_be_updated(client: AsyncClient) -> None:
    token = await _token(client, "privacy@example.com")
    await client.put(
        "/api/v1/candidates/me/profile",
        json={"full_name": "Тест Тестов", "contacts": {"email": "t@example.com"}},
        headers=_auth(token),
    )
    updated = await client.patch(
        "/api/v1/candidates/me/privacy", json={"show_contacts": True}, headers=_auth(token)
    )
    assert updated.status_code == 200
    assert updated.json()["privacy"]["show_contacts"] is True
    assert updated.json()["privacy"]["show_stack"] is True  # остальные не сброшены


async def test_generated_profile_pdf_is_valid(client: AsyncClient) -> None:
    token = await _token(client, "pdf@example.com")
    await client.put(
        "/api/v1/candidates/me/profile",
        json={
            "full_name": "Пётр Иванов",
            "specialization": "backend",
            "grade": "senior",
            "experience_years": 7,
            "stack": ["Python", "PostgreSQL", "Docker"],
            "summary": "Проектирую высоконагруженные сервисы.",
        },
        headers=_auth(token),
    )
    response = await client.get("/api/v1/candidates/me/profile/pdf", headers=_auth(token))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 800

    # PDF читается и содержит текст профиля
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(response.content))
    assert len(reader.pages) >= 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Пётр Иванов" in text


async def test_pdf_requires_existing_profile(client: AsyncClient) -> None:
    token = await _token(client, "nopdfprofile@example.com")
    response = await client.get("/api/v1/candidates/me/profile/pdf", headers=_auth(token))
    assert response.status_code == 404


@pytest.mark.parametrize("field", ["experience_years"])
async def test_validation_rejects_absurd_values(client: AsyncClient, field: str) -> None:
    token = await _token(client, "validation@example.com")
    response = await client.put("/api/v1/candidates/me/profile", json={field: 99}, headers=_auth(token))
    assert response.status_code == 422
