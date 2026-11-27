"""Dependências compartilhadas: sessão, usuário autenticado e autorização por recurso."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError, TokenType, decode_token
from app.db.session import get_session
from app.models import Plant, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep, settings: SettingsDep
) -> User:
    try:
        user_id = decode_token(token, TokenType.ACCESS, settings)
    except InvalidTokenError as exc:
        raise credentials_error() from exc
    user = await session.get(User, user_id)
    if user is None:
        raise credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_owned_plant(plant_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Plant:
    """Planta do usuário autenticado.

    Plantas de outros usuários respondem 404, como se não existissem, para não revelar
    quais ids são válidos.
    """
    plant = await session.scalar(
        select(Plant).where(Plant.id == plant_id, Plant.owner_id == user.id)
    )
    if plant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")
    return plant


OwnedPlant = Annotated[Plant, Depends(get_owned_plant)]
