#!/usr/bin/env python3
"""Создаёт образец PDF-резюме для демонстрации и smoke-проверок.

Использование: python scripts/make-sample-resume.py [путь.pdf]
"""

from __future__ import annotations

import io
import os
import sys

RESUME_LINES = [
    "Иван Петров",
    "ivan.petrov@example.com",
    "+7 999 123-45-67",
    "",
    "Backend-разработчик, senior",
    "Опыт 6 лет",
    "",
    "Стек: Python, FastAPI, PostgreSQL, Docker, Kubernetes, Redis, Kafka, Git, Linux",
    "",
    "Командная работа, менторство, ответственность за результат",
]


def build(path: str) -> str:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from app.services.profile_pdf import ensure_fonts, resolve_font_name

    ensure_fonts()
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont(resolve_font_name(), 12)
    y = 780
    for line in RESUME_LINES:
        pdf.drawString(50, y, line)
        y -= 18
    pdf.showPage()
    pdf.save()

    with open(path, "wb") as fh:
        fh.write(buffer.getvalue())
    return path


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sample-resume.pdf"
    print(build(target))
