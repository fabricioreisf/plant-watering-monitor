import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select

from app.api.deps import SessionDep
from app.models import Species
from app.schemas.species import SpeciesRead

router = APIRouter(prefix="/species", tags=["species"])


@router.get("", response_model=list[SpeciesRead])
async def list_species(
    session: SessionDep,
    q: str | None = Query(default=None, max_length=100, description="Busca por nome."),
) -> list[Species]:
    """Catálogo público de espécies, em ordem alfabética do nome popular."""
    query = select(Species).order_by(Species.common_name)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(Species.common_name.ilike(pattern), Species.scientific_name.ilike(pattern))
        )
    return list(await session.scalars(query))


@router.get("/{species_id}", response_model=SpeciesRead)
async def get_species(species_id: uuid.UUID, session: SessionDep) -> Species:
    species = await session.get(Species, species_id)
    if species is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Species not found")
    return species
