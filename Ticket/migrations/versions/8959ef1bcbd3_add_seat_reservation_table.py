"""add seat_reservation table

Revision ID: 8959ef1bcbd3
Revises: 25d958a0a8f0
Create Date: 2025-12-31 16:17:08.187066

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8959ef1bcbd3"
down_revision = "25d958a0a8f0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "seat_reservation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fahrt_id", sa.Integer(), nullable=False),
        sa.Column("zug_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="aktiv"),
        sa.Column("erstelltAm", sa.DateTime(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("ticket.id", ondelete="CASCADE"), nullable=False, unique=True),
    )
    op.create_index("ix_seat_reservation_fahrt_id", "seat_reservation", ["fahrt_id"])
    op.create_index("ix_seat_reservation_zug_id", "seat_reservation", ["zug_id"])


def downgrade():
    op.drop_index("ix_seat_reservation_zug_id", table_name="seat_reservation")
    op.drop_index("ix_seat_reservation_fahrt_id", table_name="seat_reservation")
    op.drop_table("seat_reservation")
