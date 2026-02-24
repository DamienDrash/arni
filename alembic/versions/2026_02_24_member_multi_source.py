"""Add multi-source member management: source tracking, custom columns, import logs.

Revision ID: ms01_member_multi_source
Revises: (latest)
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa

revision = "ms01_member_multi_source"
down_revision = None  # Adjust to actual latest revision in chain
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── StudioMember: add source tracking, custom fields, tags, notes ──
    op.add_column("studio_members", sa.Column("source", sa.String(), nullable=True, server_default="manual"))
    op.add_column("studio_members", sa.Column("source_id", sa.String(), nullable=True))
    op.add_column("studio_members", sa.Column("tags", sa.Text(), nullable=True))
    op.add_column("studio_members", sa.Column("custom_fields", sa.Text(), nullable=True))
    op.add_column("studio_members", sa.Column("notes", sa.Text(), nullable=True))

    op.create_index("ix_studio_members_source", "studio_members", ["source"])
    op.create_index("ix_studio_members_source_id", "studio_members", ["source_id"])

    # Backfill existing rows: set source='magicline' for all existing members
    op.execute("UPDATE studio_members SET source = 'magicline' WHERE source IS NULL OR source = 'manual'")
    # Make source NOT NULL after backfill
    op.alter_column("studio_members", "source", nullable=False, server_default="manual")

    # ── MemberCustomColumn: tenant-defined custom columns ──
    op.create_table(
        "member_custom_columns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("field_type", sa.String(), nullable=False, server_default="text"),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_custom_column_tenant_slug"),
    )

    # ── MemberImportLog: tracks import operations ──
    op.create_table(
        "member_import_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("member_import_logs")
    op.drop_table("member_custom_columns")
    op.drop_index("ix_studio_members_source_id", table_name="studio_members")
    op.drop_index("ix_studio_members_source", table_name="studio_members")
    op.drop_column("studio_members", "notes")
    op.drop_column("studio_members", "custom_fields")
    op.drop_column("studio_members", "tags")
    op.drop_column("studio_members", "source_id")
    op.drop_column("studio_members", "source")
