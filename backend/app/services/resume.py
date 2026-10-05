"""Извлечение текста из PDF-резюме."""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


class ResumeError(Exception):
    """Ошибка обработки загруженного резюме."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def extract_text_from_pdf(data: bytes, max_chars: int = 200_000) -> str:
    """Извлекает текст из PDF.

    Поддерживаются PDF с текстовым слоем. Скан без текстового слоя распознать
    нельзя — это явно сообщается, а не подменяется пустым результатом.
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not data:
        raise ResumeError("Пустой файл")

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ResumeError("PDF защищён паролем — загрузите незащищённый файл")
        pages_text = []
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception as exc:  # noqa: BLE001 — одна битая страница не должна ломать всё
                logger.warning("не удалось извлечь текст страницы: %s", exc)
                pages_text.append("")
    except PdfReadError as exc:
        raise ResumeError(f"Не удалось прочитать PDF: {exc}") from exc

    text = "\n".join(pages_text).strip()
    if not text:
        raise ResumeError(
            "В PDF не найден текстовый слой (возможно, это скан). "
            "Загрузите PDF с текстом или заполните профиль вручную."
        )
    return text[:max_chars]
