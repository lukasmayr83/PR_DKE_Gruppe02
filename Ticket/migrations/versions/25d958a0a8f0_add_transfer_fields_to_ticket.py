"""add transfer fields to ticket

Revision ID: 25d958a0a8f0
Revises: ceec5f6743a4
Create Date: 2025-12-31 13:31:36.155770

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25d958a0a8f0'
down_revision = 'ceec5f6743a4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ticket", sa.Column("fahrt_id2", sa.Integer(), nullable=True))
    op.add_column("ticket", sa.Column("halteplan_id2", sa.Integer(), nullable=True))
    op.add_column("ticket", sa.Column("zug_id2", sa.Integer(), nullable=True))
    op.add_column("ticket", sa.Column("umstieg_bahnhof", sa.String(length=120), nullable=True))
    op.add_column("ticket", sa.Column("umstieg_ankunft", sa.DateTime(), nullable=True))
    op.add_column("ticket", sa.Column("umstieg_abfahrt", sa.DateTime(), nullable=True))


def downgrade():

    pass

