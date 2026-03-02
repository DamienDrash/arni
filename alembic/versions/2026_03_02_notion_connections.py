"""Add notion_connections and notion_sync_logs tables for multi-tenant Notion integration.

Revision ID: notion_conn_001
Revises: ai_config_001
"""
from alembic import op
import sqlalchemy as sa

revision = "notion_conn_001"
down_revision = "ai_config_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Notion Connections (one per tenant) ──────────────────────────
    op.create_table(
        "notion_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("workspace_id", sa.String(255), nullable=False, default=""),
        sa.Column("workspace_name", sa.String(500), nullable=False, default=""),
        sa.Column("workspace_icon", sa.String(500), nullable=True),
        sa.Column("access_token_enc", sa.Text, nullable=False, default=""),
        sa.Column("bot_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="idle"),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(50), nullable=True),
        sa.Column("last_sync_error", sa.Text, nullable=True),
        sa.Column("webhook_active", sa.Boolean, server_default="false"),
        sa.Column("webhook_secret", sa.String(255), nullable=True),
        sa.Column("pages_synced", sa.Integer, server_default="0"),
        sa.Column("databases_synced", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_notion_connections_tenant_id", "notion_connections", ["tenant_id"])

    # ── Notion Synced Pages (track which pages are synced per tenant) ─
    op.create_table(
        "notion_synced_pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notion_page_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False, default=""),
        sa.Column("page_type", sa.String(50), nullable=False, default="page"),
        sa.Column("parent_type", sa.String(100), nullable=True),
        sa.Column("parent_name", sa.String(500), nullable=True),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("sync_enabled", sa.Boolean, server_default="true"),
        sa.Column("sync_status", sa.String(50), server_default="pending"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("last_edited_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "notion_page_id", name="uq_tenant_notion_page"),
    )
    op.create_index("ix_notion_synced_pages_tenant_id", "notion_synced_pages", ["tenant_id"])

    # ── Notion Sync Logs ─────────────────────────────────────────────
    op.create_table(
        "notion_sync_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sync_type", sa.String(50), nullable=False, default="full"),
        sa.Column("status", sa.String(50), nullable=False, default="running"),
        sa.Column("pages_processed", sa.Integer, server_default="0"),
        sa.Column("chunks_created", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
    )
    op.create_index("ix_notion_sync_logs_tenant_id", "notion_sync_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("notion_sync_logs")
    op.drop_table("notion_synced_pages")
    op.drop_table("notion_connections")
