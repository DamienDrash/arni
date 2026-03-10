"""add tenant_brand_references table

Revision ID: 2026_03_10_brand_refs
Revises: 2026_03_10_media_enrichment
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_10_brand_refs"
down_revision = "2026_03_10_media_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_brand_references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_brand_references_tenant_id", "tenant_brand_references", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_tenant_brand_references_tenant_id", "tenant_brand_references")
    op.drop_table("tenant_brand_references")
