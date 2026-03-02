"""campaign_phase1_refactoring – Add tenant_id, contact_id, channel to campaign_recipients

Revision ID: camp_phase1
Revises: camp_001
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "camp_phase1"
down_revision = "camp_001"
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    insp = inspect(conn)
    if table not in insp.get_table_names():
        return False
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def upgrade() -> None:
    conn = op.get_bind()

    # Add tenant_id to campaign_recipients
    if not _column_exists(conn, "campaign_recipients", "tenant_id"):
        op.add_column(
            "campaign_recipients",
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=True, index=True),
        )

    # Add contact_id to campaign_recipients (v2 contacts reference)
    if not _column_exists(conn, "campaign_recipients", "contact_id"):
        op.add_column(
            "campaign_recipients",
            sa.Column("contact_id", sa.Integer, nullable=True, index=True),
        )

    # Add channel to campaign_recipients
    if not _column_exists(conn, "campaign_recipients", "channel"):
        op.add_column(
            "campaign_recipients",
            sa.Column("channel", sa.String, nullable=True),
        )

    # Make member_id nullable (contacts may not have studio_members entry)
    try:
        op.alter_column(
            "campaign_recipients",
            "member_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
    except Exception:
        pass  # Already nullable or DB doesn't support alter


def downgrade() -> None:
    conn = op.get_bind()

    if _column_exists(conn, "campaign_recipients", "channel"):
        op.drop_column("campaign_recipients", "channel")
    if _column_exists(conn, "campaign_recipients", "contact_id"):
        op.drop_column("campaign_recipients", "contact_id")
    if _column_exists(conn, "campaign_recipients", "tenant_id"):
        op.drop_column("campaign_recipients", "tenant_id")
