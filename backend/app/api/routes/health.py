"""Endpoints de saúde: liveness (processo no ar) e readiness (dependências acessíveis)."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok"]


class ReadinessStatus(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


@router.get("", response_model=HealthStatus)
async def liveness() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessStatus,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessStatus}},
)
async def readiness(
    response: Response, session: AsyncSession = Depends(get_session)
) -> ReadinessStatus:
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        logger.exception("Readiness check failed: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessStatus(status="unavailable", database="unavailable")
    return ReadinessStatus(status="ok", database="ok")
