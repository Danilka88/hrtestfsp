"""Эндпоинты аутентификации, ролей и согласий."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import (
    ConsentUpdateRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPair,
    UserPublic,
    VerifyEmailRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация по email с подтверждением адреса",
)
async def register(
    payload: RegisterRequest, session: AsyncSession = Depends(get_session)
) -> RegisterResponse:
    user, token = await auth_service.register_user(
        session,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        consent_pdn=payload.consent_pdn,
        consent_publish=payload.consent_publish,
    )
    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=user.email_verified,
        message="Регистрация принята. Требуется подтверждение адреса электронной почты.",
        verification_token=token,
    )


@router.post("/verify-email", response_model=UserPublic, summary="Подтверждение адреса электронной почты")
async def verify_email(payload: VerifyEmailRequest, session: AsyncSession = Depends(get_session)) -> User:
    return await auth_service.verify_email(session, payload.token)


@router.post("/login", response_model=TokenPair, summary="Вход по email и паролю")
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    _, tokens = await auth_service.login(session, email=payload.email, password=payload.password)
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=TokenPair, summary="Обновление пары токенов (с ротацией)")
async def refresh_tokens(payload: RefreshRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    tokens = await auth_service.refresh(session, refresh_token=payload.refresh_token)
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=MessageResponse, summary="Выход (отзыв refresh-токена)")
async def logout(payload: RefreshRequest, session: AsyncSession = Depends(get_session)) -> MessageResponse:
    await auth_service.logout(session, refresh_token=payload.refresh_token)
    return MessageResponse(message="Выход выполнен")


@router.get("/me", response_model=UserPublic, summary="Текущий пользователь")
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch(
    "/consents",
    response_model=UserPublic,
    summary="Управление согласием на публикацию данных профиля",
)
async def update_consents(
    payload: ConsentUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    return await auth_service.update_publish_consent(session, user, payload.publish)
