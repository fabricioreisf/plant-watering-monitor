import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import OwnedPlant, SessionDep
from app.models import WateringLog
from app.schemas.watering import WateringCreate, WateringRead

router = APIRouter(prefix="/plants/{plant_id}/waterings", tags=["waterings"])


@router.post("", response_model=WateringRead, status_code=status.HTTP_201_CREATED)
async def create_watering(
    body: WateringCreate, plant: OwnedPlant, session: SessionDep
) -> WateringLog:
    log = WateringLog(
        plant_id=plant.id,
        watered_at=body.watered_at or datetime.now(UTC),
        amount_ml=body.amount_ml,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


@router.get("", response_model=list[WateringRead])
async def list_waterings(
    plant: OwnedPlant,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[WateringLog]:
    """Registros de rega da planta, do mais recente para o mais antigo."""
    query = (
        select(WateringLog)
        .where(WateringLog.plant_id == plant.id)
        .order_by(WateringLog.watered_at.desc(), WateringLog.id)
        .limit(limit)
        .offset(offset)
    )
    return list(await session.scalars(query))


@router.delete("/{watering_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watering(watering_id: uuid.UUID, plant: OwnedPlant, session: SessionDep) -> None:
    log = await session.scalar(
        select(WateringLog).where(WateringLog.id == watering_id, WateringLog.plant_id == plant.id)
    )
    if log is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Watering log not found")
    await session.delete(log)
    await session.commit()
