"""Тесты приглашений: статусы, раскрытие контактов, связь с ФСП."""

from __future__ import annotations

from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models.candidate import CandidateProfile
from app.models.testing import SESSION_COMPLETED
from app.models.testing import TestSession as SessionRow
from app.models.user import User
from tests.conftest import register_and_verify

CANDIDATE_EMAIL = "invited@example.com"
CANDIDATE_CONTACTS = {"email": CANDIDATE_EMAIL, "phone": "+7 999 777-66-55", "telegram": "@invited"}


async def _login_only(client: AsyncClient, email: str, password: str = "secret12345") -> str:
    """Вход для уже зарегистрированного пользователя."""
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _login(client: AsyncClient, email: str, role: str) -> str:
    await register_and_verify(client, email, role=role)
    return await _login_only(client, email)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_candidate(
    client: AsyncClient, db_factory, email: str, contacts: dict[str, str] | None = None
) -> str:
    """Кандидат с профилем, категорией и контактами."""
    await register_and_verify(client, email)
    async with db_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.add(
            CandidateProfile(
                user_id=user.id,
                full_name="Кандидат Приглашённый",
                contacts=contacts if contacts is not None else dict(CANDIDATE_CONTACTS),
                specialization="backend",
                grade="middle",
                experience_years=4,
                stack=["Python", "Docker"],
                roles=["backend"],
            )
        )
        session.add(
            SessionRow(
                user_id=user.id,
                specialization_id=1,
                target_grade="middle",
                status=SESSION_COMPLETED,
                item_count=8,
                theta=0.6,
                standard_error=0.4,
                result_grade="middle",
            )
        )
        await session.commit()
        return user.id


async def _employer(client: AsyncClient, email: str) -> str:
    token = await _login(client, email, "employer")
    await client.put(
        "/api/v1/employers/me/profile",
        json={"company_name": "ООО «Приглашения»", "description": "Тестовая компания"},
        headers=_auth(token),
    )
    return token


def _reference(user_id: str) -> str:
    return f"cand-{user_id[:8]}"


async def _send(client: AsyncClient, token: str, reference: str, **overrides) -> Response:
    payload = {
        "candidate_reference": reference,
        "message": "Приглашаем в команду платежей",
        "salary_from": 250000,
        "salary_to": 320000,
        "contact_method": "hr@company.ru",
        **overrides,
    }
    return await client.post("/api/v1/employers/me/invitations", json=payload, headers=_auth(token))


# --- Отправка и валидация -----------------------------------------------------


async def test_invitation_requires_employer_role(client: AsyncClient, db_factory) -> None:
    candidate_id = await _make_candidate(client, db_factory, "rolecand@example.com")
    token = await _login_only(client, "rolecand@example.com")
    response = await _send(client, token, _reference(candidate_id))
    assert response.status_code == 403


async def test_salary_is_mandatory(client: AsyncClient, db_factory) -> None:
    candidate_id = await _make_candidate(client, db_factory, "salcand@example.com")
    token = await _employer(client, "salemp@example.com")
    response = await client.post(
        "/api/v1/employers/me/invitations",
        json={"candidate_reference": _reference(candidate_id), "salary_from": 300000, "salary_to": 100000},
        headers=_auth(token),
    )
    assert response.status_code == 422  # нарушено правило «от ≤ до»


async def test_invitation_to_unknown_candidate(client: AsyncClient, db_factory) -> None:
    token = await _employer(client, "unknownemp@example.com")
    assert (await _send(client, token, "cand-deadbeef")).status_code == 404
    assert (await _send(client, token, "x")).status_code == 400


async def test_duplicate_active_invitation_rejected(client: AsyncClient, db_factory) -> None:
    candidate_id = await _make_candidate(client, db_factory, "dupinv@example.com")
    token = await _employer(client, "dupemp@example.com")
    assert (await _send(client, token, _reference(candidate_id))).status_code == 200
    duplicate = await _send(client, token, _reference(candidate_id))
    assert duplicate.status_code == 409


# --- Статусы и раскрытие контактов --------------------------------------------


async def test_full_invitation_lifecycle_reveals_contacts_only_on_accept(
    client: AsyncClient, db_factory
) -> None:
    candidate_id = await _make_candidate(client, db_factory, "lifecycle@example.com")
    candidate_token = await _login_only(client, "lifecycle@example.com")
    employer_token = await _employer(client, "lifecycleemp@example.com")

    created = await _send(client, employer_token, _reference(candidate_id))
    assert created.status_code == 200, created.text
    body = created.json()
    invitation_id = body["id"]
    assert body["status"] == "sent"
    assert body["contacts_revealed"] is False
    assert body["candidate_contacts"] is None
    assert body["salary_from"] == 250000 and body["salary_to"] == 320000

    # Кандидат видит условия до начала общения
    inbound = await client.get("/api/v1/candidates/me/invitations", headers=_auth(candidate_token))
    assert inbound.status_code == 200
    item = inbound.json()[0]
    assert item["company_name"] == "ООО «Приглашения»"
    assert item["salary_from"] == 250000
    assert item["status"] == "sent"

    viewed = await client.post(
        f"/api/v1/candidates/me/invitations/{invitation_id}/view", headers=_auth(candidate_token)
    )
    assert viewed.status_code == 200
    assert viewed.json()["status"] == "viewed"

    # Контакты всё ещё скрыты
    employer_view = await client.get("/api/v1/employers/me/invitations", headers=_auth(employer_token))
    assert employer_view.json()[0]["contacts_revealed"] is False

    accepted = await client.post(
        f"/api/v1/candidates/me/invitations/{invitation_id}/decision",
        json={"status": "accepted"},
        headers=_auth(candidate_token),
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    # Только теперь работодатель получает контакты
    employer_view = await client.get("/api/v1/employers/me/invitations", headers=_auth(employer_token))
    final = employer_view.json()[0]
    assert final["status"] == "accepted"
    assert final["contacts_revealed"] is True
    assert final["candidate_contacts"]["email"] == CANDIDATE_EMAIL
    assert final["candidate_contacts"]["phone"] == "+7 999 777-66-55"


async def test_decline_keeps_contacts_hidden(client: AsyncClient, db_factory) -> None:
    candidate_id = await _make_candidate(client, db_factory, "decline@example.com")
    candidate_token = await _login_only(client, "decline@example.com")
    employer_token = await _employer(client, "declineemp@example.com")

    created = await _send(client, employer_token, _reference(candidate_id))
    invitation_id = created.json()["id"]

    declined = await client.post(
        f"/api/v1/candidates/me/invitations/{invitation_id}/decision",
        json={"status": "declined"},
        headers=_auth(candidate_token),
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"

    employer_view = await client.get("/api/v1/employers/me/invitations", headers=_auth(employer_token))
    assert employer_view.json()[0]["contacts_revealed"] is False
    assert employer_view.json()[0]["candidate_contacts"] is None


async def test_second_decision_is_rejected(client: AsyncClient, db_factory) -> None:
    candidate_id = await _make_candidate(client, db_factory, "twice@example.com")
    candidate_token = await _login_only(client, "twice@example.com")
    employer_token = await _employer(client, "twiceemp@example.com")
    invitation_id = (await _send(client, employer_token, _reference(candidate_id))).json()["id"]

    url = f"/api/v1/candidates/me/invitations/{invitation_id}/decision"
    assert (
        await client.post(url, json={"status": "accepted"}, headers=_auth(candidate_token))
    ).status_code == 200
    assert (
        await client.post(url, json={"status": "declined"}, headers=_auth(candidate_token))
    ).status_code == 409


async def test_invalid_decision_value(client: AsyncClient, db_factory) -> None:
    candidate_id = await _make_candidate(client, db_factory, "badd@example.com")
    candidate_token = await _login_only(client, "badd@example.com")
    employer_token = await _employer(client, "baddemp@example.com")
    invitation_id = (await _send(client, employer_token, _reference(candidate_id))).json()["id"]

    response = await client.post(
        f"/api/v1/candidates/me/invitations/{invitation_id}/decision",
        json={"status": "maybe"},
        headers=_auth(candidate_token),
    )
    assert response.status_code == 400


# --- Изоляция -----------------------------------------------------------------


async def test_candidate_cannot_touch_foreign_invitation(client: AsyncClient, db_factory) -> None:
    target_id = await _make_candidate(client, db_factory, "target@example.com")
    await _make_candidate(client, db_factory, "intruder@example.com")
    intruder_token = await _login_only(client, "intruder@example.com")
    employer_token = await _employer(client, "isoemp@example.com")

    invitation_id = (await _send(client, employer_token, _reference(target_id))).json()["id"]

    assert (
        await client.post(
            f"/api/v1/candidates/me/invitations/{invitation_id}/view",
            headers=_auth(intruder_token),
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/candidates/me/invitations/{invitation_id}/decision",
            json={"status": "accepted"},
            headers=_auth(intruder_token),
        )
    ).status_code == 404

    own = await client.get("/api/v1/candidates/me/invitations", headers=_auth(intruder_token))
    assert own.json() == []


async def test_candidate_sees_only_own_invitations(client: AsyncClient, db_factory) -> None:
    first = await _make_candidate(client, db_factory, "first@example.com")
    await _make_candidate(client, db_factory, "second@example.com")
    second_token = await _login_only(client, "second@example.com")
    employer_token = await _employer(client, "iso2emp@example.com")

    await _send(client, employer_token, _reference(first))

    assert (await client.get("/api/v1/candidates/me/invitations", headers=_auth(second_token))).json() == []


async def test_candidate_invitations_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/candidates/me/invitations")).status_code == 401


# --- Связь с ФСП ---------------------------------------------------------------


async def test_fsp_without_link_is_explicitly_empty(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "nofsp@example.com", "candidate")
    response = await client.get("/api/v1/candidates/me/fsp", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["linked"] is False
    assert body["achievements"] == []
    assert "нет данных" in body["note"]


async def test_fsp_link_with_history(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "fspyes@example.com", "candidate")
    response = await client.put(
        "/api/v1/candidates/me/fsp", json={"fsp_id": "fsp-1001"}, headers=_auth(token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["linked"] is True
    assert body["achievements"] and body["achievements"][0]["contest"]


async def test_fsp_link_without_history_is_not_imputed(client: AsyncClient, db_factory) -> None:
    """Идентификатор привязан, но достижений нет — это не то же самое, что «нет данных»."""
    token = await _login(client, "fspempty@example.com", "candidate")
    response = await client.put(
        "/api/v1/candidates/me/fsp", json={"fsp_id": "fsp-2000"}, headers=_auth(token)
    )
    body = response.json()
    assert body["linked"] is True
    assert body["achievements"] == []
    assert "не найдено" in body["note"]


async def test_fsp_id_appears_in_profile_and_pdf(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "fspdf@example.com", "candidate")
    await client.put(
        "/api/v1/candidates/me/profile",
        json={"full_name": "С ФСП", "specialization": "backend", "declared_grade": "middle"},
        headers=_auth(token),
    )
    await client.put("/api/v1/candidates/me/fsp", json={"fsp_id": "fsp-1001"}, headers=_auth(token))

    me = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert me.json()["fsp_id"] == "fsp-1001"

    pdf = await client.get("/api/v1/candidates/me/profile/pdf", headers=_auth(token))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


async def test_fsp_can_be_unlinked(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "fspunlink@example.com", "candidate")
    await client.put("/api/v1/candidates/me/fsp", json={"fsp_id": "fsp-1001"}, headers=_auth(token))
    response = await client.put("/api/v1/candidates/me/fsp", json={"fsp_id": None}, headers=_auth(token))
    assert response.json()["linked"] is False


async def test_fsp_endpoints_require_candidate_role(client: AsyncClient, db_factory) -> None:
    token = await _login(client, "fspemp@example.com", "employer")
    assert (await client.get("/api/v1/candidates/me/fsp", headers=_auth(token))).status_code == 403


async def test_invitation_can_reference_selection(client: AsyncClient, db_factory) -> None:
    """Приглашение без обязательной привязки к вакансии, но с привязкой к подборке."""
    candidate_id = await _make_candidate(client, db_factory, "withsel@example.com")
    employer_token = await _employer(client, "selinv@example.com")

    selection = await client.post(
        "/api/v1/employers/me/needs",
        json={"title": "Backend", "specialization_code": "backend", "grade": "middle"},
        headers=_auth(employer_token),
    )
    selection_id = selection.json()["id"]
    reference = next(
        c["reference"] for c in selection.json()["candidates"] if c["reference"] == _reference(candidate_id)
    )

    response = await _send(client, employer_token, reference, selection_id=selection_id)
    assert response.status_code == 200
    assert response.json()["id"]

    listing: list[dict] = (
        await client.get("/api/v1/employers/me/invitations", headers=_auth(employer_token))
    ).json()
    assert len(listing) == 1
    assert listing[0]["status"] == "sent"


# --- Отзыв приглашения --------------------------------------------------------
#
# ТЗ требует статусы, отражающие ход взаимодействия. Отзыв — дополнение к ним:
# отправленное по ошибке приглашение не должно висеть на кандидате.


async def _revoke(client: AsyncClient, token: str, invitation_id: str) -> Response:
    return await client.post(f"/api/v1/employers/me/invitations/{invitation_id}/revoke", headers=_auth(token))


async def test_employer_revokes_invitation_before_decision(client: AsyncClient, db_factory) -> None:
    candidate_id = await _make_candidate(client, db_factory, "revokecand@example.com")
    candidate_token = await _login_only(client, "revokecand@example.com")
    employer_token = await _employer(client, "revokeemp@example.com")

    created = (await _send(client, employer_token, _reference(candidate_id))).json()
    assert created["can_revoke"] is True

    revoked = await _revoke(client, employer_token, created["id"])
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"
    # Отозванное отзывать больше нельзя, и контакты не раскрыты
    assert revoked.json()["can_revoke"] is False
    assert revoked.json()["contacts_revealed"] is False

    # Кандидат видит отзыв и не может принять решение
    inbound = (await client.get("/api/v1/candidates/me/invitations", headers=_auth(candidate_token))).json()
    assert inbound[0]["status"] == "revoked"
    decision = await client.post(
        f"/api/v1/candidates/me/invitations/{created['id']}/decision",
        json={"status": "accepted"},
        headers=_auth(candidate_token),
    )
    assert decision.status_code == 409

    # Повторный отзыв — тоже отказ
    assert (await _revoke(client, employer_token, created["id"])).status_code == 409


async def test_revoke_is_rejected_after_candidate_decided(client: AsyncClient, db_factory) -> None:
    """Решение кандидата — история, отменить его работодатель не может."""
    candidate_id = await _make_candidate(client, db_factory, "revokedecided@example.com")
    candidate_token = await _login_only(client, "revokedecided@example.com")
    employer_token = await _employer(client, "revokedecidedemp@example.com")

    created = (await _send(client, employer_token, _reference(candidate_id))).json()
    await client.post(
        f"/api/v1/candidates/me/invitations/{created['id']}/decision",
        json={"status": "declined"},
        headers=_auth(candidate_token),
    )
    response = await _revoke(client, employer_token, created["id"])
    assert response.status_code == 409


async def test_revoke_touches_only_own_invitations(client: AsyncClient, db_factory) -> None:
    candidate_id = await _make_candidate(client, db_factory, "revokeown@example.com")
    author = await _employer(client, "revokeauthor@example.com")
    stranger = await _employer(client, "revokestranger@example.com")
    candidate_token = await _login_only(client, "revokeown@example.com")

    created = (await _send(client, author, _reference(candidate_id))).json()
    # Чужой работодатель не должен узнать о существовании записи — ответ как у несуществующей
    assert (await _revoke(client, stranger, created["id"])).status_code == 404
    # Кандидат отзывать не может: это действие стороны работодателя
    assert (await _revoke(client, candidate_token, created["id"])).status_code == 403


async def test_revoked_invitation_does_not_block_new_one(client: AsyncClient, db_factory) -> None:
    """После отзыва работодатель может отправить приглашение заново с другими условиями."""
    candidate_id = await _make_candidate(client, db_factory, "revokenew@example.com")
    employer_token = await _employer(client, "revokenewemp@example.com")

    created = (await _send(client, employer_token, _reference(candidate_id))).json()
    await _revoke(client, employer_token, created["id"])

    again = await _send(
        client, employer_token, _reference(candidate_id), salary_from=300000, salary_to=350000
    )
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "sent"
    assert again.json()["salary_from"] == 300000
