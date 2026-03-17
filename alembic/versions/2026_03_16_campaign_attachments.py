"""Add attachment_url and attachment_filename to campaigns table.

Revision ID: 2026_03_16_campaign_attachments
Revises: 2026_03_16_merge_campaign_heads
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_16_campaign_attachments"
down_revision = "2026_03_16_merge_campaign_heads"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (idempotent migrations)."""
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def upgrade() -> None:
    if not _column_exists("campaigns", "attachment_url"):
        op.add_column("campaigns", sa.Column("attachment_url", sa.String(512), nullable=True))
    if not _column_exists("campaigns", "attachment_filename"):
        op.add_column("campaigns", sa.Column("attachment_filename", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("campaigns", "attachment_filename")
    op.drop_column("campaigns", "attachment_url")
