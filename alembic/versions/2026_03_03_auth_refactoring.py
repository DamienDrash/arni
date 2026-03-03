"""Auth Refactoring: Add fields for email verification, password reset,
account lockout, DSGVO consent, MFA, refresh tokens, session management,
team invitations, and onboarding.

Revision ID: auth_refactoring_001
Revises: merge_all_heads_001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "auth_refactoring_001"
down_revision = "merge_all_heads_001"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists in a table."""
    bind = op.get_bind()
    insp = sa_inspect(bind)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def _table_exists(table: str) -> bool:
    """Check if a table already exists."""
    bind = op.get_bind()
    insp = sa_inspect(bind)
    return table in insp.get_table_names()


def _safe_add_column(table: str, column: sa.Column) -> None:
    """Add a column only if it doesn't already exist."""
    if not _column_exists(table, column.name):
        op.add_column(table, column)


def upgrade() -> None:
    # ─── UserAccount (users table) ──────────────────────────────────────
    # Email verification
    _safe_add_column("users", sa.Column("email_verified", sa.Boolean(), server_default="false", nullable=False))
    _safe_add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    _safe_add_column("users", sa.Column("email_verification_token", sa.String(), nullable=True))
    _safe_add_column("users", sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True))

    # Password reset
    _safe_add_column("users", sa.Column("password_reset_token", sa.String(), nullable=True))
    _safe_add_column("users", sa.Column("password_reset_sent_at", sa.DateTime(), nullable=True))
    _safe_add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))

    # Account lockout
    _safe_add_column("users", sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False))
    _safe_add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))
    _safe_add_column("users", sa.Column("last_failed_login_at", sa.DateTime(), nullable=True))

    # MFA
    _safe_add_column("users", sa.Column("mfa_enabled", sa.Boolean(), server_default="false", nullable=False))
    _safe_add_column("users", sa.Column("mfa_secret_encrypted", sa.String(), nullable=True))
    _safe_add_column("users", sa.Column("mfa_backup_codes_hash", sa.Text(), nullable=True))
    _safe_add_column("users", sa.Column("mfa_enabled_at", sa.DateTime(), nullable=True))

    # Tracking
    _safe_add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))

    # Make password_hash nullable for future passwordless/SSO users
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=True)

    # ─── Tenant (tenants table) ─────────────────────────────────────────
    # DSGVO consent
    _safe_add_column("tenants", sa.Column("tos_accepted_at", sa.DateTime(), nullable=True))
    _safe_add_column("tenants", sa.Column("privacy_accepted_at", sa.DateTime(), nullable=True))

    # Session configuration
    _safe_add_column("tenants", sa.Column("session_idle_timeout_minutes", sa.Integer(), server_default="30", nullable=False))
    _safe_add_column("tenants", sa.Column("session_absolute_timeout_hours", sa.Integer(), server_default="720", nullable=False))

    # MFA enforcement
    _safe_add_column("tenants", sa.Column("mfa_required", sa.Boolean(), server_default="false", nullable=False))

    # Onboarding
    _safe_add_column("tenants", sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True))

    # ─── Pending Invitations ────────────────────────────────────────────
    if not _table_exists("pending_invitations"):
        op.create_table(
            "pending_invitations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("role", sa.String(), server_default="tenant_user", nullable=False),
            sa.Column("token", sa.String(), unique=True, nullable=False, index=True),
            sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("accepted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    # ─── Refresh Tokens ─────────────────────────────────────────────────
    if not _table_exists("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("token_hash", sa.String(), unique=True, nullable=False, index=True),
            sa.Column("family_id", sa.String(), nullable=False, index=True),
            sa.Column("device_info", sa.String(), nullable=True),
            sa.Column("ip_address", sa.String(), nullable=True),
            sa.Column("is_revoked", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    # ─── User Sessions (Device Management) ──────────────────────────────
    if not _table_exists("user_sessions"):
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("jti", sa.String(), unique=True, nullable=False, index=True),
            sa.Column("refresh_token_id", sa.Integer(), sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True),
            sa.Column("device_name", sa.String(), nullable=True),
            sa.Column("ip_address", sa.String(), nullable=True),
            sa.Column("user_agent", sa.String(), nullable=True),
            sa.Column("last_active_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("user_sessions")
    op.drop_table("refresh_tokens")
    op.drop_table("pending_invitations")

    # Tenant columns
    for col in ("onboarding_completed_at", "mfa_required", "session_absolute_timeout_hours",
                "session_idle_timeout_minutes", "privacy_accepted_at", "tos_accepted_at"):
        op.drop_column("tenants", col)

    # User columns
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)
    for col in ("last_login_at", "mfa_enabled_at", "mfa_backup_codes_hash", "mfa_secret_encrypted",
                "mfa_enabled", "last_failed_login_at", "locked_until", "failed_login_attempts",
                "password_changed_at", "password_reset_sent_at", "password_reset_token",
                "email_verification_sent_at", "email_verification_token",
                "email_verified_at", "email_verified"):
        op.drop_column("users", col)
