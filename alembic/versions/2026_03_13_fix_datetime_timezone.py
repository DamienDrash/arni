"""fix: convert auth datetime columns to TIMESTAMPTZ

Revision ID: 2026_03_13_fix_tz
Revises: 2026_03_10_addon_img_quota
Create Date: 2026-03-13

Root cause: email_verification_sent_at and related columns were TIMESTAMP WITHOUT TIME ZONE.
PostgreSQL strips tzinfo on write → naive datetime returned on read → TypeError when
comparing with datetime.now(timezone.utc). Gold standard: always use TIMESTAMPTZ.
"""
from alembic import op

revision = '2026_03_13_fix_tz'
down_revision = '2026_03_10_addon_img_quota'
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = [
        'email_verified_at',
        'email_verification_sent_at',
        'password_reset_sent_at',
        'password_changed_at',
    ]
    for col in cols:
        op.execute(
            f"ALTER TABLE users ALTER COLUMN {col} "
            f"TYPE TIMESTAMPTZ USING {col} AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    cols = [
        'email_verified_at',
        'email_verification_sent_at',
        'password_reset_sent_at',
        'password_changed_at',
    ]
    for col in cols:
        op.execute(f"ALTER TABLE users ALTER COLUMN {col} TYPE TIMESTAMP WITHOUT TIME ZONE")
