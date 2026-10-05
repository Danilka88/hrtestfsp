"""Генерация стандартизированного PDF-профиля кандидата.

Шрифт выбирается из списка кандидатов с поддержкой кириллицы: в контейнере
устанавливается fonts-dejavu-core, локально используются системные шрифты.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

logger = logging.getLogger(__name__)

FONT_NAME = "ProfileFont"
FONT_BOLD_NAME = "ProfileFont-Bold"

# Пары (обычный, полужирный) в порядке предпочтения.
_FONT_CANDIDATES = [
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
]

_fonts_ready = False
_font_available = False


def ensure_fonts() -> bool:
    """Регистрирует шрифт с кириллицей. Возвращает True, если он найден."""
    global _fonts_ready, _font_available
    if _fonts_ready:
        return _font_available

    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, regular))
                bold_path = bold if os.path.exists(bold) else regular
                pdfmetrics.registerFont(TTFont(FONT_BOLD_NAME, bold_path))
                _font_available = True
                logger.info("PDF-профиль: используется шрифт %s", regular)
                break
            except Exception as exc:  # noqa: BLE001 — некорректный шрифт не должен ломать запрос
                logger.warning("не удалось зарегистрировать шрифт %s: %s", regular, exc)

    if not _font_available:
        logger.warning(
            "Шрифт с поддержкой кириллицы не найден — PDF будет собран стандартным "
            "шрифтом; кириллица может отображаться некорректно"
        )
    _fonts_ready = True
    return _font_available


def resolve_font_name(regular: bool = True) -> str:
    """Имя зарегистрированного шрифта (или стандартного, если кириллического нет)."""
    if _font_available:
        return FONT_NAME if regular else FONT_BOLD_NAME
    return "Helvetica" if regular else "Helvetica-Bold"


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title",
            fontName=resolve_font_name(False),
            fontSize=18,
            leading=22,
            spaceAfter=2 * mm,
            textColor=colors.HexColor("#0f172a"),
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName=resolve_font_name(),
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#475569"),
            spaceAfter=6 * mm,
        ),
        "heading": ParagraphStyle(
            "heading",
            fontName=resolve_font_name(False),
            fontSize=12,
            leading=15,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            textColor=colors.HexColor("#0f172a"),
        ),
        "body": ParagraphStyle(
            "body",
            fontName=resolve_font_name(),
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#1e293b"),
        ),
    }


def _p(text: str | None, style: ParagraphStyle) -> Paragraph | None:
    value = (text or "").strip()
    return Paragraph(escape(value), style) if value else None


def build_profile_pdf(profile: dict[str, Any], fsp_achievements: list[dict[str, Any]] | None = None) -> bytes:
    """Собирает PDF-профиль. Отсутствующие данные не выдумываются — блок пропускается."""
    ensure_fonts()
    styles = _styles()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Профиль кандидата",
        author="IT-Talent Match",
    )

    story: list[Any] = []
    story.append(Paragraph("Профиль кандидата", styles["title"]))
    story.append(
        Paragraph(
            f"Специализация: {escape(profile.get('specialization') or 'не указана')} · "
            f"Грейд: {escape(profile.get('grade') or 'не определён')}",
            styles["subtitle"],
        )
    )

    story.append(Paragraph("Основные сведения", styles["heading"]))
    rows = [
        ("ФИО", profile.get("full_name")),
        ("Опыт, лет", profile.get("experience_years")),
        ("Роли", ", ".join(profile.get("roles") or [])),
        ("Стек", ", ".join(profile.get("stack") or [])),
        ("Софт-скиллы", ", ".join(profile.get("soft_skills") or [])),
    ]
    for label, value in rows:
        if value in (None, "", []):
            continue
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(value))}", styles["body"]))

    summary = _p(profile.get("summary"), styles["body"])
    if summary is not None:
        story.append(Paragraph("О себе", styles["heading"]))
        story.append(summary)

    contacts = profile.get("contacts") or {}
    visible_contacts = {k: v for k, v in contacts.items() if v}
    if visible_contacts and profile.get("privacy", {}).get("show_contacts", False):
        story.append(Paragraph("Контакты", styles["heading"]))
        for key, value in visible_contacts.items():
            story.append(Paragraph(f"<b>{escape(str(key))}:</b> {escape(str(value))}", styles["body"]))

    if fsp_achievements:
        story.append(Paragraph("Подтверждённые достижения", styles["heading"]))
        for item in fsp_achievements:
            place = f" — {item['place']} место" if item.get("place") else ""
            story.append(
                Paragraph(
                    f"{escape(str(item.get('contest', '')))} ({item.get('year', '')}){escape(place)}",
                    styles["body"],
                )
            )

    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Документ сформирован автоматически платформой подбора ИТ-специалистов.",
            styles["subtitle"],
        )
    )

    doc.build(story)
    return buffer.getvalue()
