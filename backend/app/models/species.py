from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class Species(UUIDPrimaryKeyMixin, Base):
    """Espécie da base de conhecimento. A chave natural é o nome científico."""

    __tablename__ = "species"
    __table_args__ = (
        CheckConstraint("kc > 0 AND kc <= 1.5", name="kc_range"),
        CheckConstraint(
            "drying_threshold > 0 AND drying_threshold < 1", name="drying_threshold_range"
        ),
    )

    scientific_name: Mapped[str] = mapped_column(String(200), unique=True)
    common_name: Mapped[str] = mapped_column(String(200))
    kc: Mapped[float]
    drying_threshold: Mapped[float]
    watering_instructions: Mapped[str] = mapped_column(Text)
