"""ticket-abfahrt-ankunft-cascades

Revision ID: a693db793988
Revises: 4dc56523629e
Create Date: 2025-12-18 19:23:58.306694

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a693db793988'
down_revision = '4dc56523629e'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # SQLite: keine constraint drops (unnamed constraints -> ValueError)
    with op.batch_alter_table("ticket", schema=None) as batch_op:
        batch_op.add_column(sa.Column("abfahrt", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("ankunft", sa.DateTime(), nullable=True))

    # Optional: falls es schon Tickets gab, fülle leere Werte sinnvoll
    op.execute('UPDATE ticket SET abfahrt = erstelltAm WHERE abfahrt IS NULL')
    op.execute('UPDATE ticket SET ankunft = erstelltAm WHERE ankunft IS NULL')


def downgrade():
    with op.batch_alter_table("ticket", schema=None) as batch_op:
        batch_op.drop_column("ankunft")
        batch_op.drop_column("abfahrt")


    # ### end Alembic commands ###
