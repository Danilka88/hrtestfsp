"""Аналитика платформы для кабинета администратора.

Метрики выбраны по практике двусторонних платформ: состояние рынка измеряется не
числом пользователей, а тем, находят ли стороны друг друга. Отсюда основной набор:
воронка пути кандидата, ликвидность (доля потребностей, доведённых до приглашения),
сбалансированность спроса и предложения по категориям, время до первого ответа.

Все запросы — только чтение, ничего не меняют. Пустые значения не подменяются
нулями там, где это искажало бы смысл: где данных нет, возвращается `None`, и
интерфейс показывает «нет данных».
"""

from __future__ import annotations

from datetime import timedelta
from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models.candidate import CandidateProfile
from app.models.employer import EmployerNeed, EmployerProfile, Selection
from app.models.invitation import (
    STATUS_ACCEPTED,
    STATUS_DECLINED,
    STATUS_REVOKED,
    STATUS_SENT,
    STATUS_VIEWED,
    Invitation,
)
from app.models.marketplace import Application, RegularTask, Vacancy
from app.models.testing import SESSION_COMPLETED, Specialization, TestSession
from app.models.user import User, UserRole

# Порог «свежести» активности профиля и «зависшего» приглашения
ACTIVE_DAYS = 30
STALE_INVITATION_DAYS = 7


async def _scalar(session: AsyncSession, stmt: Any) -> int:
    return int((await session.execute(stmt)).scalar() or 0)


async def _count(session: AsyncSession, model: Any, *conditions: Any) -> int:
    stmt = select(func.count()).select_from(model)
    for condition in conditions:
        stmt = stmt.where(condition)
    return await _scalar(session, stmt)


def _share(part: int, total: int) -> float | None:
    """Доля в процентах. None, если считать не от чего — это не «0%», а «нет данных»."""
    if total <= 0:
        return None
    return round(part / total * 100, 1)


async def overview(session: AsyncSession) -> dict[str, Any]:
    """Ключевые показатели, воронка кандидата и ликвидность рынка."""
    now = utcnow()
    active_since = now - timedelta(days=ACTIVE_DAYS)

    candidates = await _count(session, User, User.role == UserRole.CANDIDATE)
    employers = await _count(session, User, User.role == UserRole.EMPLOYER)
    verified = await _count(session, User, User.is_active.is_(True))

    with_profile = await _count(session, CandidateProfile, CandidateProfile.full_name.isnot(None))
    tested = await _scalar(
        session,
        select(func.count(func.distinct(TestSession.user_id))).where(TestSession.status == SESSION_COMPLETED),
    )
    categorized = await _count(
        session,
        CandidateProfile,
        CandidateProfile.specialization.isnot(None),
        CandidateProfile.grade.isnot(None),
    )
    invited = await _scalar(session, select(func.count(func.distinct(Invitation.candidate_user_id))))
    responded = await _scalar(
        session,
        select(func.count(func.distinct(Invitation.candidate_user_id))).where(
            Invitation.status.in_([STATUS_ACCEPTED, STATUS_DECLINED])
        ),
    )
    accepted = await _scalar(
        session,
        select(func.count(func.distinct(Invitation.candidate_user_id))).where(
            Invitation.status == STATUS_ACCEPTED
        ),
    )

    # Ликвидность: насколько потребности превращаются в реальные контакты
    needs_total = await _count(session, EmployerNeed)
    needs_with_selection = await _scalar(session, select(func.count(func.distinct(Selection.need_id))))
    needs_with_invitation = await _scalar(
        session,
        select(func.count(func.distinct(Invitation.need_id))).where(Invitation.need_id.isnot(None)),
    )

    invitations_total = await _count(session, Invitation)
    invitations_answered = await _count(
        session, Invitation, Invitation.status.in_([STATUS_ACCEPTED, STATUS_DECLINED])
    )
    invitations_accepted = await _count(session, Invitation, Invitation.status == STATUS_ACCEPTED)
    invitations_stale = await _count(
        session,
        Invitation,
        Invitation.status.in_([STATUS_SENT, STATUS_VIEWED]),
        Invitation.created_at < now - timedelta(days=STALE_INVITATION_DAYS),
    )

    # Время до первого ответа кандидата — метрика, которую чувствует соискатель
    decided = (
        await session.execute(
            select(Invitation.created_at, Invitation.decided_at).where(
                Invitation.decided_at.isnot(None),
                Invitation.status.in_([STATUS_ACCEPTED, STATUS_DECLINED]),
            )
        )
    ).all()
    response_hours = sorted(
        (decided_at - created_at).total_seconds() / 3600
        for created_at, decided_at in decided
        if decided_at is not None and created_at is not None
    )

    active_candidates = await _count(session, CandidateProfile, CandidateProfile.updated_at >= active_since)
    active_employers = await _scalar(
        session,
        select(func.count(func.distinct(Invitation.employer_id))).where(
            Invitation.created_at >= active_since
        ),
    )
    with_fsp = await _count(session, User, User.role == UserRole.CANDIDATE, User.fsp_id.isnot(None))

    vacancies_open = await _count(session, Vacancy, Vacancy.status == "published")
    applications_total = await _count(session, Application)
    tasks_total = await _count(session, RegularTask)

    return {
        "generated_at": now,
        "people": {
            "candidates": candidates,
            "employers": employers,
            "active_candidates": active_candidates,
            "active_employers": active_employers,
            "verified_accounts": verified,
            "candidate_employer_ratio": (round(candidates / employers, 2) if employers else None),
        },
        "funnel": [
            {
                "key": "registered",
                "title": "Зарегистрировались",
                "value": candidates,
                "share": 100.0 if candidates else None,
                "hint": "создали аккаунт соискателя",
            },
            {
                "key": "profile",
                "title": "Заполнили профиль",
                "value": with_profile,
                "share": _share(with_profile, candidates),
                "hint": "указано имя — профиль готов к подбору",
            },
            {
                "key": "tested",
                "title": "Прошли тест",
                "value": tested,
                "share": _share(tested, candidates),
                "hint": "завершена хотя бы одна сессия тестирования",
            },
            {
                "key": "categorized",
                "title": "Получили категорию",
                "value": categorized,
                "share": _share(categorized, candidates),
                "hint": "специализация и грейд присвоены — кандидат виден в подборке",
            },
            {
                "key": "invited",
                "title": "Получили приглашение",
                "value": invited,
                "share": _share(invited, candidates),
                "hint": "работодатель вышел на контакт первым",
            },
            {
                "key": "responded",
                "title": "Ответили на приглашение",
                "value": responded,
                "share": _share(responded, candidates),
                "hint": "приняли или отклонили — работодатель получил ответ",
            },
            {
                "key": "accepted",
                "title": "Приняли приглашение",
                "value": accepted,
                "share": _share(accepted, candidates),
                "hint": "контакты раскрыты, стороны начали общение",
            },
        ],
        "liquidity": {
            "needs_total": needs_total,
            "needs_with_selection": needs_with_selection,
            "needs_with_invitation": needs_with_invitation,
            "selection_rate": _share(needs_with_selection, needs_total),
            "contact_rate": _share(needs_with_invitation, needs_total),
            "invitations_total": invitations_total,
            "invitations_answered": invitations_answered,
            "invitations_accepted": invitations_accepted,
            "invitations_stale": invitations_stale,
            "response_rate": _share(invitations_answered, invitations_total),
            "accept_rate": _share(invitations_accepted, invitations_total),
            "response_hours_median": round(median(response_hours), 1) if response_hours else None,
        },
        "coverage": {
            "with_fsp": with_fsp,
            "fsp_share": _share(with_fsp, candidates),
            "vacancies_open": vacancies_open,
            "applications_total": applications_total,
            "tasks_total": tasks_total,
        },
    }


async def categories(session: AsyncSession) -> list[dict[str, Any]]:
    """Спрос и предложение по категориям: где рынок сбалансирован, а где пусто.

    Предложение — кандидаты с присвоенной категорией, спрос — потребности
    работодателей той же связки «специализация × грейд» плюс направленные
    приглашения. Разница показывает, куда платформе стоит привлекать людей.
    """
    specializations = {
        row.code: row.title for row in (await session.execute(select(Specialization))).scalars().all()
    }

    supply_rows = (
        await session.execute(
            select(
                CandidateProfile.specialization,
                CandidateProfile.grade,
                func.count().label("candidates"),
            )
            .where(
                CandidateProfile.specialization.isnot(None),
                CandidateProfile.grade.isnot(None),
            )
            .group_by(CandidateProfile.specialization, CandidateProfile.grade)
        )
    ).all()

    needs_rows = (
        await session.execute(
            select(
                Specialization.code,
                EmployerNeed.grade_code,
                func.count().label("needs"),
            )
            .join(Specialization, Specialization.id == EmployerNeed.specialization_id)
            .group_by(Specialization.code, EmployerNeed.grade_code)
        )
    ).all()

    invitation_rows = (
        await session.execute(
            select(
                CandidateProfile.specialization,
                CandidateProfile.grade,
                func.count().label("invitations"),
            )
            .join(User, User.id == CandidateProfile.user_id)
            .join(Invitation, Invitation.candidate_user_id == User.id)
            .group_by(CandidateProfile.specialization, CandidateProfile.grade)
        )
    ).all()

    supply: dict[tuple[str, str], int] = {}
    demand: dict[tuple[str, str], int] = {}
    invites: dict[tuple[str, str], int] = {}

    for code, grade, count in supply_rows:
        supply[(code, grade)] = int(count)
    for code, grade, count in needs_rows:
        key = (code, grade or "")
        demand[key] = demand.get(key, 0) + int(count)
    for code, grade, count in invitation_rows:
        invites[(code, grade)] = int(count)

    keys = sorted(set(supply) | set(demand) | set(invites))
    result: list[dict[str, Any]] = []
    for key in keys:
        code, grade = key
        candidates = supply.get(key, 0)
        needs = demand.get(key, 0)
        sent = invites.get(key, 0)
        if not candidates and not needs and not sent:
            continue
        if candidates == 0 and needs > 0:
            balance = "дефицит"
        elif needs == 0 and candidates > 0:
            balance = "нет спроса"
        elif needs and candidates >= needs * 3:
            balance = "переизбыток"
        else:
            balance = "сбалансировано"
        result.append(
            {
                "specialization": code,
                "specialization_title": specializations.get(code, code),
                "grade": grade or None,
                "candidates": candidates,
                "needs": needs,
                "invitations": sent,
                "balance": balance,
                "supply_per_need": round(candidates / needs, 2) if needs else None,
            }
        )
    result.sort(key=lambda item: (-item["needs"], -item["candidates"]))
    return result


async def companies(session: AsyncSession) -> list[dict[str, Any]]:
    """Активность работодателей: кто действительно выходит на контакт."""
    rows = (
        await session.execute(
            select(
                EmployerProfile.user_id,
                EmployerProfile.company_name,
                EmployerProfile.industry,
            )
        )
    ).all()

    invitations = (
        await session.execute(
            select(
                Invitation.employer_id,
                Invitation.status,
            )
        )
    ).all()
    by_employer: dict[str, dict[str, int]] = {}
    for employer_id, status in invitations:
        bucket = by_employer.setdefault(employer_id, {})
        bucket[status] = bucket.get(status, 0) + 1

    vacancies = dict(
        (await session.execute(select(Vacancy.employer_id, func.count()).group_by(Vacancy.employer_id))).all()
    )
    needs = dict(
        (
            await session.execute(
                select(EmployerNeed.employer_id, func.count()).group_by(EmployerNeed.employer_id)
            )
        ).all()
    )

    result: list[dict[str, Any]] = []
    for user_id, name, industry in rows:
        bucket = by_employer.get(user_id, {})
        sent = sum(bucket.values())
        answered = bucket.get(STATUS_ACCEPTED, 0) + bucket.get(STATUS_DECLINED, 0)
        result.append(
            {
                "employer_id": user_id,
                "company_name": name,
                "industry": industry,
                "needs": int(needs.get(user_id, 0)),
                "invitations": sent,
                "accepted": bucket.get(STATUS_ACCEPTED, 0),
                "declined": bucket.get(STATUS_DECLINED, 0),
                "revoked": bucket.get(STATUS_REVOKED, 0),
                "waiting": bucket.get(STATUS_SENT, 0) + bucket.get(STATUS_VIEWED, 0),
                "response_rate": _share(answered, sent),
                "vacancies": int(vacancies.get(user_id, 0)),
            }
        )
    result.sort(key=lambda item: (-item["invitations"], item["company_name"] or ""))
    return result


async def interactions(session: AsyncSession, limit: int = 60) -> dict[str, Any]:
    """Схема взаимодействия: узлы обеих сторон и связи-приглашения между ними.

    Возвращает минимальный набор для отрисовки: компания, кандидат, статус связи
    и время. Ограничение по количеству — чтобы схема оставалась читаемой.
    """
    rows = (
        await session.execute(
            select(
                Invitation.id,
                Invitation.employer_id,
                Invitation.candidate_user_id,
                Invitation.status,
                Invitation.created_at,
                EmployerProfile.company_name,
                CandidateProfile.full_name,
                CandidateProfile.specialization,
                CandidateProfile.grade,
            )
            .join(EmployerProfile, EmployerProfile.user_id == Invitation.employer_id)
            .join(CandidateProfile, CandidateProfile.user_id == Invitation.candidate_user_id)
            .order_by(Invitation.created_at.desc())
            .limit(limit)
        )
    ).all()

    employers: dict[str, dict[str, Any]] = {}
    candidates: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    for (
        inv_id,
        employer_id,
        candidate_id,
        status,
        created_at,
        company,
        full_name,
        specialization,
        grade,
    ) in rows:
        employers.setdefault(employer_id, {"id": employer_id, "label": company or "Компания без названия"})
        candidates.setdefault(
            candidate_id,
            {
                "id": candidate_id,
                "label": full_name or "Кандидат без имени",
                "specialization": specialization,
                "grade": grade,
            },
        )
        edges.append(
            {
                "id": inv_id,
                "employer_id": employer_id,
                "candidate_id": candidate_id,
                "status": status,
                "created_at": created_at,
            }
        )

    return {
        "employers": list(employers.values()),
        "candidates": list(candidates.values()),
        "edges": edges,
        "truncated": len(edges) >= limit,
    }


async def anomalies(session: AsyncSession) -> list[dict[str, Any]]:
    """Сигналы, требующие внимания администратора. Проверки простые и объяснимые.

    Ничего не «предсказывается»: каждое наблюдение — следствие конкретных данных,
    поэтому рядом с ним указывается, что именно проверено и сколько записей задето.
    """
    now = utcnow()
    found: list[dict[str, Any]] = []

    # 1. Потребности без подборки: работодатель описал запрос, но выдачи нет
    needs_without_selection = (
        await session.execute(
            select(func.count())
            .select_from(EmployerNeed)
            .where(~EmployerNeed.id.in_(select(Selection.need_id).where(Selection.need_id.isnot(None))))
        )
    ).scalar() or 0
    if needs_without_selection:
        found.append(
            {
                "key": "needs_without_selection",
                "severity": "warning",
                "title": "Потребности без подборки",
                "detail": f"{needs_without_selection} запросов работодателей не получили подборку",
                "hint": "проверьте, что в этих категориях есть кандидаты",
            }
        )

    # 2. Зависшие приглашения: отправлены, но кандидат не ответил дольше недели
    stale = (
        await session.execute(
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.status.in_([STATUS_SENT, STATUS_VIEWED]),
                Invitation.created_at < now - timedelta(days=STALE_INVITATION_DAYS),
            )
        )
    ).scalar() or 0
    if stale:
        found.append(
            {
                "key": "stale_invitations",
                "severity": "info",
                "title": "Приглашения без ответа",
                "detail": f"{stale} приглашений старше {STALE_INVITATION_DAYS} дней без решения кандидата",
                "hint": (
                    "напомните кандидату или отзовите приглашение, чтобы не держать работодателя в ожидании"
                ),
            }
        )

    # 3. Работодатели без единого приглашения: аккаунт есть, механика не используется
    employers_idle = (
        await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.role == UserRole.EMPLOYER,
                ~User.id.in_(select(Invitation.employer_id).distinct()),
            )
        )
    ).scalar() or 0
    if employers_idle:
        found.append(
            {
                "key": "employers_without_invitations",
                "severity": "info",
                "title": "Работодатели без приглашений",
                "detail": f"{employers_idle} компаний ещё не выходили на контакт",
                "hint": "основная механика платформы — приглашение, а не отклик",
            }
        )

    # 4. Кандидаты без теста: профиль заполнен, категории нет
    untested = (
        await session.execute(
            select(func.count())
            .select_from(CandidateProfile)
            .where(CandidateProfile.specialization.is_(None))
        )
    ).scalar() or 0
    if untested:
        found.append(
            {
                "key": "candidates_without_category",
                "severity": "warning",
                "title": "Кандидаты без категории",
                "detail": f"{untested} профилей не прошли тест — в подборке они не видны",
                "hint": "обязательный путь кандидата: опрос → грейд → тест → категория",
            }
        )

    # 5. Одинаковые названия компаний: сигнал возможного дублирования аккаунтов
    duplicates = (
        await session.execute(
            select(EmployerProfile.company_name, func.count().label("n"))
            .where(EmployerProfile.company_name.isnot(None))
            .group_by(EmployerProfile.company_name)
            .having(func.count() > 1)
        )
    ).all()
    if duplicates:
        names = ", ".join(f"«{name}» ×{n}" for name, n in duplicates[:5])
        found.append(
            {
                "key": "duplicate_companies",
                "severity": "warning",
                "title": "Повторяющиеся компании",
                "detail": f"найдено совпадений названий: {names}",
                "hint": "вне MVP верификация компаний не автоматизирована — проверьте вручную",
            }
        )

    # 6. Перекос спроса и предложения по категориям
    rows = await categories(session)
    deficit = [row for row in rows if row["balance"] == "дефицит"]
    if deficit:
        preview = ", ".join(
            f"{row['specialization_title']} / {row['grade'] or 'грейд не указан'}" for row in deficit[:3]
        )
        found.append(
            {
                "key": "supply_deficit",
                "severity": "warning",
                "title": "Дефицит кандидатов",
                "detail": f"категорий без кандидатов при наличии спроса: {len(deficit)} ({preview})",
                "hint": "куда стоит направлять привлечение соискателей",
            }
        )

    return found
