"""sync language column

Revision ID: de02ce9f6c7b
Revises: 2026_02_22_enable_rls
Create Date: 2026-02-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'de02ce9f6c7b'
down_revision = '2026_02_22_enable_rls'
branch_labels = None
depends_on = None

def upgrade():
    # Column already exists in DB, so we just satisfy Alembic
    pass

def downgrade():
    pass
