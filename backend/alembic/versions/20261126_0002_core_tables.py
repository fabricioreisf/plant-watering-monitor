"""core tables: users, species, plants, watering_logs

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "species",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scientific_name", sa.String(length=200), nullable=False),
        sa.Column("common_name", sa.String(length=200), nullable=False),
        sa.Column("kc", sa.Float(), nullable=False),
        sa.Column("drying_threshold", sa.Float(), nullable=False),
        sa.Column("watering_instructions", sa.Text(), nullable=False),
        sa.CheckConstraint("kc > 0 AND kc <= 1.5", name=op.f("ck_species_kc_range")),
        sa.CheckConstraint(
            "drying_threshold > 0 AND drying_threshold < 1",
            name=op.f("ck_species_drying_threshold_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_species")),
        sa.UniqueConstraint("scientific_name", name=op.f("uq_species_scientific_name")),
    )
    op.create_table(
        "plants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("species_id", sa.Uuid(), nullable=False),
        sa.Column("nickname", sa.String(length=100), nullable=False),
        sa.Column(
            "environment",
            sa.Enum("indoor", "outdoor", name="environment", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("pot_volume_liters", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # Mesmo nome que o modelo gera para o Enum (convenção ck_<tabela>_<nome>).
        sa.CheckConstraint(
            "environment IN ('indoor', 'outdoor')", name=op.f("ck_plants_environment")
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name=op.f("ck_plants_latitude_range")),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_plants_longitude_range")
        ),
        sa.CheckConstraint("pot_volume_liters > 0", name=op.f("ck_plants_pot_volume_positive")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_plants_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["species_id"],
            ["species.id"],
            name=op.f("fk_plants_species_id_species"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plants")),
    )
    op.create_index(op.f("ix_plants_owner_id"), "plants", ["owner_id"])
    op.create_table(
        "watering_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plant_id", sa.Uuid(), nullable=False),
        sa.Column("watered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_ml", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "amount_ml IS NULL OR amount_ml > 0", name=op.f("ck_watering_logs_amount_positive")
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"],
            ["plants.id"],
            name=op.f("fk_watering_logs_plant_id_plants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watering_logs")),
    )
    op.create_index(
        "ix_watering_logs_plant_id_watered_at", "watering_logs", ["plant_id", "watered_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_watering_logs_plant_id_watered_at", table_name="watering_logs")
    op.drop_table("watering_logs")
    op.drop_index(op.f("ix_plants_owner_id"), table_name="plants")
    op.drop_table("plants")
    op.drop_table("species")
    op.drop_table("users")
