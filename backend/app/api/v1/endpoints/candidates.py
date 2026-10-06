"""Эндпоинты кабинета кандидата: профиль и резюме."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.user import User, UserRole
from app.schemas.candidate import (
    CandidateProfileIn,
    CandidateProfileOut,
    ParsedResume,
    PrivacyUpdateRequest,
    ResumeUploadResponse,
)
from app.services import candidates as candidate_service
from app.services import fsp_link
from app.services.profile_pdf import build_profile_pdf

router = APIRouter(prefix="/candidates/me", tags=["candidates"])

MAX_RESUME_BYTES = 5 * 1024 * 1024

candidate_only = require_roles(UserRole.CANDIDATE)


@router.get("/profile", response_model=CandidateProfileOut, summary="Профиль кандидата")
async def get_profile(
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileOut:
    profile = await candidate_service.get_profile(session, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Профиль ещё не создан")
    return CandidateProfileOut.model_validate(profile)


@router.put("/profile", response_model=CandidateProfileOut, summary="Заполнить/обновить профиль по форме")
async def put_profile(
    payload: CandidateProfileIn,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileOut:
    profile = await candidate_service.upsert_profile(session, user.id, payload)
    return CandidateProfileOut.model_validate(profile)


@router.post(
    "/resume",
    response_model=ResumeUploadResponse,
    summary="Загрузить PDF-резюме с автораспознаванием",
)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> ResumeUploadResponse:
    if (file.content_type or "").lower() not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=415, detail="Ожидается файл в формате PDF")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Файл больше 5 МБ")

    profile, parsed, chars = await candidate_service.apply_resume_upload(
        session, user.id, filename=file.filename or "resume.pdf", data=data
    )

    return ResumeUploadResponse(
        profile=CandidateProfileOut.model_validate(profile),
        parsed=ParsedResume.model_validate(parsed),
        text_chars=chars,
        message="Резюме распознано и добавлено в профиль. Проверьте данные перед публикацией.",
    )


@router.patch("/privacy", response_model=CandidateProfileOut, summary="Настройки приватности профиля")
async def patch_privacy(
    payload: PrivacyUpdateRequest,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileOut:
    profile = await candidate_service.get_profile(session, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Профиль ещё не создан")
    updated = await candidate_service.update_privacy(session, profile, payload)
    return CandidateProfileOut.model_validate(updated)


@router.get(
    "/profile/pdf",
    summary="Скачать стандартизированный PDF-профиль",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_profile_pdf(
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> Response:
    profile = await candidate_service.get_profile(session, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Профиль ещё не создан")

    # Достижения ФСП добавляются в PDF, только если идентификатор привязан и реестр ответил
    achievements = None
    if user.fsp_id:
        status = await fsp_link.status(session, user)
        achievements = status.get("achievements") or None

    pdf_bytes = build_profile_pdf(candidate_service.pdf_payload(profile), achievements)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="candidate-profile.pdf"'},
    )
