"""enable_rls

Revision ID: 2026_02_22_enable_rls
Revises: fadf7c20edd1
Create Date: 2026-02-22 12:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_02_22_enable_rls'
down_revision = 'fadf7c20edd1'
branch_labels = None
depends_on = None

TENANT_TABLES = [
    'chat_sessions',
    'chat_messages',
    'settings',
    'users',
    'audit_logs',
    'studio_members',
    'tenant_configs',
    'member_feedback',
    'usage_records'
]

def upgrade() -> None:
    # We only want to apply this if we're on PostgreSQL
    conn = op.get_bind()
    if conn.engine.name != 'postgresql':
        return

    for table in TENANT_TABLES:
        # 1. Enable RLS
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        # 2. Force RLS (so it applies to table owners as well)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        # 3. Create Policy
        # The policy allows access if:
        # - app.current_tenant_id is not set (NULL or empty) -> bypass (for background tasks/admin)
        # - app.current_tenant_id matches the row's tenant_id
        policy_sql = f"""
        CREATE POLICY tenant_isolation_policy ON {table}
        AS PERMISSIVE FOR ALL
        USING (
            current_setting('app.current_tenant_id', true) IS NULL
            OR current_setting('app.current_tenant_id', true) = ''
            OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int
        );
        """
        op.execute(policy_sql)

def downgrade() -> None:
    conn = op.get_bind()
    if conn.engine.name != 'postgresql':
        return

    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
