import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, OwnedPlant, SessionDep
from app.models import Plant, Species
from app.schemas.plant import PlantCreate, PlantRead, PlantUpdate

router = APIRouter(prefix="/plants", tags=["plants"])


async def _ensure_species_exists(session: SessionDep, species_id: uuid.UUID) -> None:
    if await session.get(Species, species_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown species_id")


async def _reload(session: SessionDep, plant: Plant) -> Plant:
    # Recarrega valores gerados no banco (timestamps) e a espécie associada.
    await session.refresh(plant)
    return plant


@router.post("", response_model=PlantRead, status_code=status.HTTP_201_CREATED)
async def create_plant(body: PlantCreate, user: CurrentUser, session: SessionDep) -> Plant:
    await _ensure_species_exists(session, body.species_id)
    plant = Plant(owner_id=user.id, **body.model_dump())
    session.add(plant)
    await session.commit()
    return await _reload(session, plant)


@router.get("", response_model=list[PlantRead])
async def list_plants(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Plant]:
    query = (
        select(Plant)
        .where(Plant.owner_id == user.id)
        .order_by(Plant.created_at, Plant.id)
        .limit(limit)
        .offset(offset)
    )
    return list(await session.scalars(query))


@router.get("/{plant_id}", response_model=PlantRead)
async def get_plant(plant: OwnedPlant) -> Plant:
    return plant


@router.patch("/{plant_id}", response_model=PlantRead)
async def update_plant(body: PlantUpdate, plant: OwnedPlant, session: SessionDep) -> Plant:
    changes = body.model_dump(exclude_unset=True)
    if "species_id" in changes:
        await _ensure_species_exists(session, changes["species_id"])
    for field, value in changes.items():
        setattr(plant, field, value)
    await session.commit()
    return await _reload(session, plant)


@router.delete("/{plant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plant(plant: OwnedPlant, session: SessionDep) -> None:
    await session.delete(plant)
    await session.commit()
