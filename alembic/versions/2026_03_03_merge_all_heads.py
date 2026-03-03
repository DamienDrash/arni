"""Merge all migration heads into a single head

This migration merges all independent migration branches into a single
linear history. No schema changes are made.

Revision ID: merge_all_heads_001
Revises: 001_rls_policies, 002_integration_registry, cf01_contacts_v2,
         camp_phase4, 2026_03_02_contact_sync_refactoring,
         notion_conn_001, billing_v2_001
Create Date: 2026-03-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "merge_all_heads_001"
down_revision: Union[str, Sequence[str]] = (
    "001_rls_policies",
    "002_integration_registry",
    "cf01_contacts_v2",
    "camp_phase4",
    "2026_03_02_contact_sync_refactoring",
    "notion_conn_001",
    "billing_v2_001",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge point – no schema changes."""
    pass


def downgrade() -> None:
    """Merge point – no schema changes."""
    pass
