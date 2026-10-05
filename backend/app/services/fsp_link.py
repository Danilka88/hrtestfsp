"""Связь профиля кандидата с идентификатором участника ФСП.

API и структура данных реестра не предоставлены, поэтому доступ идёт через
провайдер за интерфейсом. Обязательное требование: корректная обработка случая,
когда истории у кандидата нет.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.providers.registry import get_fsp


async def link(session: AsyncSession, user: User, fsp_id: str | None) -> None:
    user.fsp_id = (fsp_id or "").strip() or None
    await session.commit()
    await session.refresh(user)


async def status(session: AsyncSession, user: User) -> dict[str, Any]:
    """Состояние связи: без идентификатора, без истории или с достижениями."""
    if not user.fsp_id:
        return {
            "fsp_id": None,
            "linked": False,
            "achievements": [],
            "note": (
                "Профиль не связан с участником ФСП. Кандидат без истории ФСП "
                "корректно обрабатывается: соответствующие блоки помечаются как «нет данных»."
            ),
        }

    achievements: list[dict[str, Any]] = []
    error: str | None = None
    try:
        for item in await get_fsp().fetch_achievements(user.fsp_id):
            achievements.append(
                {
                    "contest": item.contest,
                    "category": item.category,
                    "year": item.year,
                    "place": item.place,
                    "rating": item.rating,
                }
            )
    except Exception as exc:  # noqa: BLE001 — недоступность реестра не должна ломать профиль
        error = str(exc)

    if error:
        note = f"Идентификатор ФСП привязан, но реестр недоступен: {error}"
    elif not achievements:
        note = (
            "Идентификатор ФСП привязан, подтверждённых достижений не найдено. "
            "Блок достижений отображается как «нет данных»."
        )
    else:
        note = f"Подтверждено достижений: {len(achievements)}"

    return {
        "fsp_id": user.fsp_id,
        "linked": True,
        "achievements": achievements,
        "note": note,
    }
