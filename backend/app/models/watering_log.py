import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WateringLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Rega informada pelo usuário. `amount_ml` nulo significa "rega completa"."""

    __tablename__ = "watering_logs"
    __table_args__ = (
        CheckConstraint("amount_ml IS NULL OR amount_ml > 0", name="amount_positive"),
        Index("ix_watering_logs_plant_id_watered_at", "plant_id", "watered_at"),
    )

    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="CASCADE"))
    watered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount_ml: Mapped[int | None]
