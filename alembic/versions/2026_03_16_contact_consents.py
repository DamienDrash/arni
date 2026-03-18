"""feat(consent): add contact_consents table for DSGVO compliance.

Revision ID: 2026_03_16_contact_consents
Revises: 2026_03_16_seed_swarm
Create Date: 2026-03-16
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "2026_03_16_contact_consents"
down_revision = "2026_03_16_seed_swarm"
branch_labels = None
depends_on = None

def _table_exists(conn, table: str) -> bool:
    try:
        return table in inspect(conn).get_table_names()
    except Exception:
        return False

def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "contact_consents"):
        op.create_table(
            "contact_consents",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("contact_id", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(50), nullable=False),
            sa.Column("consent_given", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("given_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("consent_source", sa.String(50), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("optin_token", sa.String(255), nullable=True, unique=True),
        )
        op.create_index("ix_contact_consents_tenant_contact", "contact_consents", ["tenant_id", "contact_id"])

def downgrade() -> None:
    op.drop_table("contact_consents")
