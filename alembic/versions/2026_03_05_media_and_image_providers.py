"""Add media assets, image providers, and featured image columns.

Revision ID: 2026_03_05_media_image
Revises: 2026_03_03_merge_all_heads
Create Date: 2026-03-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "2026_03_05_media_image"
down_revision = "merge_all_heads_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Platform Image Provider Registry ────────────────────────────────────
    op.create_table(
        "ai_image_providers",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("api_base_url", sa.String(512), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("supported_models_json", sa.Text, nullable=True),
        sa.Column("default_model", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # ── Tenant Image Provider (BYOK) ─────────────────────────────────────────
    op.create_table(
        "ai_tenant_image_providers",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("ai_image_providers.id"), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("preferred_model", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("tenant_id", "provider_id", name="uq_tenant_image_provider"),
    )

    # ── Media Assets ─────────────────────────────────────────────────────────
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(64), nullable=True),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="upload"),
        sa.Column("alt_text", sa.String(255), nullable=True),
        sa.Column("generation_prompt", sa.Text, nullable=True),
        sa.Column("image_provider_slug", sa.String(64), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    # ── Campaigns: featured image columns ────────────────────────────────────
    with op.batch_alter_table("campaigns") as batch_op:
        batch_op.add_column(sa.Column("featured_image_url", sa.String(512), nullable=True))
        batch_op.add_column(sa.Column("featured_image_asset_id", sa.Integer, nullable=True))

    # ── Campaign Templates: featured image ───────────────────────────────────
    with op.batch_alter_table("campaign_templates") as batch_op:
        batch_op.add_column(sa.Column("featured_image_url", sa.String(512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("campaign_templates") as batch_op:
        batch_op.drop_column("featured_image_url")

    with op.batch_alter_table("campaigns") as batch_op:
        batch_op.drop_column("featured_image_asset_id")
        batch_op.drop_column("featured_image_url")

    op.drop_table("media_assets")
    op.drop_table("ai_tenant_image_providers")
    op.drop_table("ai_image_providers")
