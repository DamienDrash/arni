"""feat(ingestion): create ingestion_jobs table for async file ingestion pipeline.

Revision ID: 2026_03_16_ingestion_jobs
Revises: 2026_03_15_restore_fks
Create Date: 2026-03-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "2026_03_16_ingestion_jobs"
down_revision = "2026_03_15_restore_fks"
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    try:
        return table in inspect(conn).get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "ingestion_jobs"):
        return  # idempotent

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("s3_key", sa.String(1000), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed", "dead_letter",
                name="ingestionjobstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_category", sa.String(100), nullable=True),
        sa.Column("chunks_total", sa.Integer(), nullable=True),
        sa.Column("chunks_processed", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_ingestion_jobs_tenant_id", "ingestion_jobs", ["tenant_id"])
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])
    op.create_index("ix_ingestion_jobs_tenant_status", "ingestion_jobs", ["tenant_id", "status"])
    op.create_index("ix_ingestion_jobs_tenant_created", "ingestion_jobs", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_tenant_created", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_tenant_status", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_tenant_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS ingestionjobstatus"))
