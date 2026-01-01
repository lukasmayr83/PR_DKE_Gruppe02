"""drop seat_reservation table

Revision ID: e1b2c3d4e5f6
Revises: 8959ef1bcbd3
Create Date: 2026-01-01 22:15:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e1b2c3d4e5f6"
down_revision = "8959ef1bcbd3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_seat_reservation_zug_id", table_name="seat_reservation")
    op.drop_index("ix_seat_reservation_fahrt_id", table_name="seat_reservation")
    op.drop_table("seat_reservation")


def downgrade():
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
