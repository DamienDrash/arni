"""Add idempotency_key column to analytics_events.

Revision ID: 2026_03_17_analytics_idempotency
Revises: 2026_03_17_orchestrator_manager
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa

revision = "2026_03_17_analytics_idempotency"
down_revision = "2026_03_17_orchestrator_manager"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analytics_events",
        sa.Column("idempotency_key", sa.String(128), nullable=True),
    )
    op.create_index(
        "uq_ae_idempotency",
        "analytics_events",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ae_idempotency", table_name="analytics_events")
    op.drop_column("analytics_events", "idempotency_key")
