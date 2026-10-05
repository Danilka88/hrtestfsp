"""Тесты извлечения текста из PDF-резюме.

Проверяются именно отказы: пустой файл, PDF без текстового слоя, защищённый
паролем и битая страница. Пользователь должен получить понятное объяснение, а
не пустой профиль.
"""

from __future__ import annotations

import pytest

from app.services.resume import ResumeError, extract_text_from_pdf


def pdf_stub() -> bytes:
    """Минимальная ASCII-заглушка PDF: содержимое подменяется в самом тесте."""
    return b"%PDF-1.4 stub"


def _pdf(tmp_path, text: str) -> bytes:
    """Собирает настоящий PDF с текстовым слоем (reportlab уже в зависимостях)."""
    from reportlab.pdfgen import canvas

    path = tmp_path / "resume.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 720, text)
    pdf.showPage()
    pdf.save()
    return path.read_bytes()


def test_extracts_text_from_real_pdf(tmp_path) -> None:
    text = extract_text_from_pdf(_pdf(tmp_path, "Python PostgreSQL Docker"))
    assert "Python" in text and "PostgreSQL" in text


def test_empty_file_is_rejected() -> None:
    with pytest.raises(ResumeError) as error:
        extract_text_from_pdf(b"")
    assert "Пустой файл" in str(error.value)


async def test_pdf_without_text_layer_is_reported(tmp_path) -> None:
    """Скан без текстового слоя — честная ошибка, а не пустой профиль."""
    from reportlab.pdfgen import canvas

    path = tmp_path / "scan.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.rect(72, 600, 200, 100, stroke=1, fill=0)  # только графика, текста нет
    pdf.showPage()
    pdf.save()

    with pytest.raises(ResumeError) as error:
        extract_text_from_pdf(path.read_bytes())
    assert "текстовый слой" in str(error.value)


def test_encrypted_pdf_is_rejected(monkeypatch) -> None:
    import pypdf

    class _Encrypted:
        is_encrypted = True

    monkeypatch.setattr(pypdf, "PdfReader", lambda stream: _Encrypted())
    with pytest.raises(ResumeError) as error:
        extract_text_from_pdf(pdf_stub())
    assert "защищён паролем" in str(error.value)


def test_unreadable_pdf_is_reported(monkeypatch) -> None:
    """Битый файл: сообщение должно объяснять причину, а не падать трассировкой."""
    import pypdf
    from pypdf.errors import PdfReadError

    def broken(stream):
        raise PdfReadError("не удалось разобрать структуру")

    monkeypatch.setattr(pypdf, "PdfReader", broken)
    with pytest.raises(ResumeError) as error:
        extract_text_from_pdf(pdf_stub())
    assert "Не удалось прочитать PDF" in str(error.value)


def test_broken_page_does_not_break_whole_document(monkeypatch, caplog) -> None:
    """Одна повреждённая страница не должна терять остальной текст."""
    import logging

    import pypdf

    class _Page:
        def __init__(self, text: str | None = None, fail: bool = False) -> None:
            self._text = text
            self._fail = fail

        def extract_text(self) -> str:
            if self._fail:
                raise ValueError("повреждённый поток")
            return self._text or ""

    class _Reader:
        is_encrypted = False
        pages = [_Page("Первый раздел"), _Page(fail=True), _Page("Третий раздел")]

    monkeypatch.setattr(pypdf, "PdfReader", lambda stream: _Reader())

    with caplog.at_level(logging.WARNING, logger="app.services.resume"):
        text = extract_text_from_pdf(pdf_stub())

    assert "Первый раздел" in text and "Третий раздел" in text
    assert "не удалось извлечь текст страницы" in caplog.text


def test_text_is_truncated_to_limit(tmp_path) -> None:
    data = _pdf(tmp_path, "Python " * 200)
    text = extract_text_from_pdf(data, max_chars=20)
    assert len(text) == 20
