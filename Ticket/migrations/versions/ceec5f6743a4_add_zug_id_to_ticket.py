"""add zug_id to ticket

Revision ID: ceec5f6743a4
Revises: a693db793988
Create Date: 2025-12-31 01:06:28.338863

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ceec5f6743a4'
down_revision = 'a693db793988'
branch_labels = None
depends_on = None




def upgrade():
    # SQLite-safe: einfach Spalte hinzufügen
    op.add_column("ticket", sa.Column("zug_id", sa.Integer(), nullable=True))


def downgrade():
    # SQLite kann DROP COLUMN je nach Version nicht sauber -> für Demo ok:
    # op.drop_column("ticket", "zug_id")
    pass
