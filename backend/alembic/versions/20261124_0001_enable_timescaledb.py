"""enable timescaledb extension

Revision ID: 0001
Revises:
Create Date: 2026-11-24

As hypertables (sensor_readings, weather_readings) das próximas fases dependem dela.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS timescaledb")
