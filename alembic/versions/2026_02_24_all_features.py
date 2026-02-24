"""all features

Revision ID: 202602240001
Revises: fadf7c20edd1
Create Date: 2026-02-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602240001'
down_revision: Union[str, None] = 'de02ce9f6c7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create member_custom_columns
    op.create_table('member_custom_columns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('field_type', sa.String(), nullable=False),
        sa.Column('options', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), default=0),
        sa.Column('is_visible', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_member_column_slug')
    )
    op.create_index(op.f('ix_member_custom_columns_id'), 'member_custom_columns', ['id'], unique=False)
    op.create_index(op.f('ix_member_custom_columns_tenant_id'), 'member_custom_columns', ['tenant_id'], unique=False)

    # 2. Create member_import_logs
    op.create_table('member_import_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('total_rows', sa.Integer(), default=0),
        sa.Column('imported', sa.Integer(), default=0),
        sa.Column('updated', sa.Integer(), default=0),
        sa.Column('skipped', sa.Integer(), default=0),
        sa.Column('errors', sa.Integer(), default=0),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_member_import_logs_id'), 'member_import_logs', ['id'], unique=False)
    op.create_index(op.f('ix_member_import_logs_tenant_id'), 'member_import_logs', ['tenant_id'], unique=False)

    # 3. Create tenant_addons
    op.create_table('tenant_addons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('addon_slug', sa.String(), nullable=False),
        sa.Column('stripe_subscription_item_id', sa.String(), nullable=True),
        sa.Column('quantity', sa.Integer(), default=1),
        sa.Column('status', sa.String(), default="active"),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenant_addons_id'), 'tenant_addons', ['id'], unique=False)
    op.create_index(op.f('ix_tenant_addons_tenant_id'), 'tenant_addons', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_tenant_addons_tenant', 'tenant_addons', 'tenants', ['tenant_id'], ['id'])

    # 4. Update studio_members
    with op.batch_alter_table('studio_members', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(), server_default='manual', nullable=False))
        batch_op.add_column(sa.Column('source_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('tags', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('custom_fields', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))

    # 5. Update plans
    with op.batch_alter_table('plans', schema=None) as batch_op:
        # Limits
        batch_op.add_column(sa.Column('max_connectors', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('ai_tier', sa.String(), server_default='basic', nullable=False))
        batch_op.add_column(sa.Column('monthly_tokens', sa.Integer(), server_default='100000', nullable=False))
        
        # New Channels
        batch_op.add_column(sa.Column('instagram_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('facebook_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('google_business_enabled', sa.Boolean(), server_default='false', nullable=False))
        
        # New Features
        batch_op.add_column(sa.Column('advanced_analytics_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('branding_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('audit_log_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('automation_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('api_access_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('multi_source_members_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('churn_prediction_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('vision_ai_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('white_label_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('sla_guarantee_enabled', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('on_premise_enabled', sa.Boolean(), server_default='false', nullable=False))
        
        # Overage Pricing
        batch_op.add_column(sa.Column('overage_conversation_cents', sa.Integer(), server_default='5', nullable=True))
        batch_op.add_column(sa.Column('overage_user_cents', sa.Integer(), server_default='1500', nullable=True))
        batch_op.add_column(sa.Column('overage_connector_cents', sa.Integer(), server_default='4900', nullable=True))
        batch_op.add_column(sa.Column('overage_channel_cents', sa.Integer(), server_default='2900', nullable=True))


def downgrade() -> None:
    # 5. Revert plans
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.drop_column('overage_channel_cents')
        batch_op.drop_column('overage_connector_cents')
        batch_op.drop_column('overage_user_cents')
        batch_op.drop_column('overage_conversation_cents')
        batch_op.drop_column('on_premise_enabled')
        batch_op.drop_column('sla_guarantee_enabled')
        batch_op.drop_column('white_label_enabled')
        batch_op.drop_column('vision_ai_enabled')
        batch_op.drop_column('churn_prediction_enabled')
        batch_op.drop_column('multi_source_members_enabled')
        batch_op.drop_column('api_access_enabled')
        batch_op.drop_column('automation_enabled')
        batch_op.drop_column('audit_log_enabled')
        batch_op.drop_column('branding_enabled')
        batch_op.drop_column('advanced_analytics_enabled')
        batch_op.drop_column('google_business_enabled')
        batch_op.drop_column('facebook_enabled')
        batch_op.drop_column('instagram_enabled')
        batch_op.drop_column('monthly_tokens')
        batch_op.drop_column('ai_tier')
        batch_op.drop_column('max_connectors')

    # 4. Revert studio_members
    with op.batch_alter_table('studio_members', schema=None) as batch_op:
        batch_op.drop_column('notes')
        batch_op.drop_column('custom_fields')
        batch_op.drop_column('tags')
        batch_op.drop_column('source_id')
        batch_op.drop_column('source')

    # 3. Drop tenant_addons
    op.drop_index(op.f('ix_tenant_addons_tenant_id'), table_name='tenant_addons')
    op.drop_index(op.f('ix_tenant_addons_id'), table_name='tenant_addons')
    op.drop_table('tenant_addons')

    # 2. Drop member_import_logs
    op.drop_index(op.f('ix_member_import_logs_tenant_id'), table_name='member_import_logs')
    op.drop_index(op.f('ix_member_import_logs_id'), table_name='member_import_logs')
    op.drop_table('member_import_logs')

    # 1. Drop member_custom_columns
    op.drop_index(op.f('ix_member_custom_columns_tenant_id'), table_name='member_custom_columns')
    op.drop_index(op.f('ix_member_custom_columns_id'), table_name='member_custom_columns')
    op.drop_table('member_custom_columns')
