import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.water_balance import Environment
from app.schemas.species import SpeciesRead

Nickname = Annotated[str, Field(min_length=1, max_length=100)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
PotVolume = Annotated[float, Field(gt=0, le=1000, description="Volume do vaso em litros.")]


class PlantCreate(BaseModel):
    species_id: uuid.UUID
    nickname: Nickname
    environment: Environment
    latitude: Latitude
    longitude: Longitude
    pot_volume_liters: PotVolume


class PlantUpdate(BaseModel):
    """Atualização parcial: só os campos enviados são alterados."""

    species_id: uuid.UUID | None = None
    nickname: Nickname | None = None
    environment: Environment | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    pot_volume_liters: PotVolume | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> Self:
        # Omitir um campo mantém o valor atual; enviar null não faz sentido para nenhum deles.
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise ValueError(f"fields cannot be null: {', '.join(nulls)}")
        return self


class PlantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nickname: str
    environment: Environment
    latitude: float
    longitude: float
    pot_volume_liters: float
    species: SpeciesRead
    created_at: datetime
    updated_at: datetime
