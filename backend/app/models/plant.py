import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.water_balance import Environment
from app.models.species import Species


class Plant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plants"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("pot_volume_liters > 0", name="pot_volume_positive"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    species_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("species.id", ondelete="RESTRICT"))
    nickname: Mapped[str] = mapped_column(String(100))
    environment: Mapped[Environment] = mapped_column(
        Enum(
            Environment,
            name="environment",
            native_enum=False,
            create_constraint=True,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    latitude: Mapped[float]
    longitude: Mapped[float]
    pot_volume_liters: Mapped[float]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    species: Mapped[Species] = relationship(lazy="joined")
