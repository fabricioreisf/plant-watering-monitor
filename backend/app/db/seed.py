"""Carrega a base curada de espécies. Idempotente: pode rodar a cada deploy.

Uso: ``python -m app.db.seed``
"""

import asyncio
import json
import logging
from importlib.resources import files

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import event_loop_factory, get_engine, get_sessionmaker
from app.models import Species
from app.schemas.species import SpeciesData

logger = logging.getLogger(__name__)

_species_list = TypeAdapter(list[SpeciesData])


def load_species_seed() -> list[SpeciesData]:
    raw = files("app.db.seeds").joinpath("species.json").read_text(encoding="utf-8")
    return _species_list.validate_python(json.loads(raw))


async def seed_species(session: AsyncSession, data: list[SpeciesData] | None = None) -> int:
    """Insere ou atualiza as espécies pelo nome científico. Retorna quantas foram inseridas."""
    data = load_species_seed() if data is None else data
    existing = {
        species.scientific_name: species
        for species in await session.scalars(
            select(Species).where(Species.scientific_name.in_([d.scientific_name for d in data]))
        )
    }
    inserted = 0
    for item in data:
        species = existing.get(item.scientific_name)
        if species is None:
            session.add(Species(**item.model_dump()))
            inserted += 1
        else:
            for key, value in item.model_dump().items():
                setattr(species, key, value)
    await session.commit()
    return inserted


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    async with get_sessionmaker()() as session:
        inserted = await seed_species(session)
    await get_engine().dispose()
    logger.info("Species seed applied: %d inserted", inserted)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=event_loop_factory)
