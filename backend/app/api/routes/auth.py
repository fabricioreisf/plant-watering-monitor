from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, SessionDep, SettingsDep, credentials_error
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.schemas.auth import RefreshRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(tags=["auth"])


def _token_response(user: User, settings: SettingsDep) -> TokenResponse:
    pair = create_token_pair(user.id, settings)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: SessionDep) -> User:
    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    await session.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    """Login no formato OAuth2 password (campo `username` = e-mail), usado também pelo /docs."""
    user = await session.scalar(select(User).where(User.email == form.username.strip().lower()))
    if not verify_password(form.password, user.password_hash if user else None):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    assert user is not None  # garantido por verify_password
    return _token_response(user, settings)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest, session: SessionDep, settings: SettingsDep
) -> TokenResponse:
    try:
        user_id = decode_token(body.refresh_token, TokenType.REFRESH, settings)
    except InvalidTokenError as exc:
        raise credentials_error() from exc
    user = await session.get(User, user_id)
    if user is None:
        raise credentials_error()
    return _token_response(user, settings)


@router.get("/users/me", response_model=UserRead, tags=["users"])
async def read_me(user: CurrentUser) -> User:
    return user
