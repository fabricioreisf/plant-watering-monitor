import uuid

from pydantic import BaseModel, ConfigDict, Field


class SpeciesData(BaseModel):
    """Dados de uma espécie como ficam na base curada (seed) e na API."""

    scientific_name: str = Field(min_length=1, max_length=200)
    common_name: str = Field(min_length=1, max_length=200)
    kc: float = Field(gt=0, le=1.5, description="Coeficiente da planta (ET_planta = Kc * ET0).")
    drying_threshold: float = Field(
        gt=0, lt=1, description="Umidade do vaso (0 a 1) abaixo da qual é hora de regar."
    )
    watering_instructions: str = Field(min_length=1)


class SpeciesRead(SpeciesData):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
