"""Add Row-Level Security (RLS) policies for tenant isolation.

Revision ID: 001_rls_policies
Revises: (latest existing migration)
Create Date: 2026-03-01

@ARCH: Phase 1, Meilenstein 1.2 – Strikte Datenisolation
Enables PostgreSQL RLS on all tenant-scoped tables.
Every query must set `app.current_tenant_id` via SET LOCAL
to access data. Without it, queries return empty results.
"""

from alembic import op

# revision identifiers
revision = "001_rls_policies"
down_revision = None  # Will be set to latest existing migration
branch_labels = None
depends_on = None

# Tables that require RLS (all tenant-scoped tables)
RLS_TABLES = [
    "chat_sessions",
    "chat_messages",
    "settings",
    "tenant_configs",
    "member_feedback",
    "audit_logs",
]


def upgrade() -> None:
    """Enable RLS and create policies for tenant isolation."""

    for table in RLS_TABLES:
        # Enable RLS on the table
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")

        # Force RLS even for table owners (important for superuser safety)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")

        # Create the isolation policy
        # Reads: only rows where tenant_id matches the session variable
        op.execute(f"""
            CREATE POLICY tenant_isolation_policy ON {table}
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer
            );
        """)

        # Create a permissive policy for INSERT (tenant_id must match)
        op.execute(f"""
            CREATE POLICY tenant_insert_policy ON {table}
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer
            );
        """)

    # Create a bypass role for platform admin operations (migrations, maintenance)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ariia_platform_admin') THEN
                CREATE ROLE ariia_platform_admin;
            END IF;
        END
        $$;
    """)

    # Platform admin bypasses RLS
    for table in RLS_TABLES:
        op.execute(f"""
            CREATE POLICY platform_admin_bypass ON {table}
            FOR ALL
            TO ariia_platform_admin
            USING (true)
            WITH CHECK (true);
        """)


def downgrade() -> None:
    """Remove RLS policies and disable RLS."""
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS platform_admin_bypass ON {table};")
        op.execute(f"DROP POLICY IF EXISTS tenant_insert_policy ON {table};")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP ROLE IF EXISTS ariia_platform_admin;")
