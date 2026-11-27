import uuid
from datetime import UTC, datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

# Tolerância para relógios levemente adiantados no cliente.
MAX_CLOCK_SKEW = timedelta(minutes=5)


class WateringCreate(BaseModel):
    watered_at: AwareDatetime | None = Field(
        default=None, description="Quando a rega aconteceu. Padrão: agora."
    )
    amount_ml: int | None = Field(
        default=None,
        gt=0,
        le=100_000,
        description="Quantidade aproximada. Vazio significa rega completa (até escorrer).",
    )

    @field_validator("watered_at")
    @classmethod
    def not_in_future(cls, value: datetime | None) -> datetime | None:
        if value is not None and value > datetime.now(UTC) + MAX_CLOCK_SKEW:
            raise ValueError("watered_at cannot be in the future")
        return value


class WateringRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    watered_at: datetime
    amount_ml: int | None
    created_at: datetime
