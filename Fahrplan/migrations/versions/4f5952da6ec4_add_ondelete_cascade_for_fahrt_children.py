"""add ondelete cascade for fahrt children

Revision ID: 4f5952da6ec4
Revises: 745aeb035496
Create Date: 2026-01-07 18:59:36.748981

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f5952da6ec4'
down_revision = '745aeb035496'
branch_labels = None
depends_on = None


from alembic import op
import sqlalchemy as sa


def upgrade():
    # --- Cleanup von halb ausgeführten Versuchen (SQLite-safe) ---
    op.execute("DROP INDEX IF EXISTS ix_dienstzuweisung_fahrt_id;")

    # Child-Tabellen droppen (wenn sie existieren)
    op.execute("DROP TABLE IF EXISTS fahrt_segment;")
    op.execute("DROP TABLE IF EXISTS fahrt_halt;")
    op.execute("DROP TABLE IF EXISTS dienstzuweisung;")

    # --- dienstzuweisung neu erstellen (mit ON DELETE CASCADE) ---
    op.create_table(
        "dienstzuweisung",
        sa.Column("dienst_id", sa.Integer(), primary_key=True),
        sa.Column("fahrt_id", sa.Integer(), nullable=False),
        sa.Column("mitarbeiter_id", sa.Integer(), nullable=False),

        sa.ForeignKeyConstraint(
            ["fahrt_id"],
            ["fahrtdurchfuehrung.fahrt_id"],
            ondelete="CASCADE",
            name="fk_dienstzuweisung_fahrt",
        ),
        sa.ForeignKeyConstraint(
            ["mitarbeiter_id"],
            ["mitarbeiter.id"],
            ondelete="CASCADE",
            name="fk_dienstzuweisung_mitarbeiter",
        ),
    )

    op.create_index("ix_dienstzuweisung_fahrt_id", "dienstzuweisung", ["fahrt_id"])

    # --- fahrt_halt neu erstellen (mit ON DELETE CASCADE) ---
    op.create_table(
        "fahrt_halt",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fahrt_id", sa.Integer(), nullable=False),
        sa.Column("bahnhof_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("ankunft_zeit", sa.DateTime(), nullable=True),
        sa.Column("abfahrt_zeit", sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(
            ["fahrt_id"],
            ["fahrtdurchfuehrung.fahrt_id"],
            ondelete="CASCADE",
            name="fk_fahrt_halt_fahrt",
        ),
        sa.ForeignKeyConstraint(
            ["bahnhof_id"],
            ["bahnhof.id"],
            ondelete="RESTRICT",
            name="fk_fahrt_halt_bahnhof",
        ),
        sa.UniqueConstraint("fahrt_id", "position", name="uq_fahrt_halt_pos"),
    )

    # --- fahrt_segment neu erstellen (mit ON DELETE CASCADE) ---
    op.create_table(
        "fahrt_segment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fahrt_id", sa.Integer(), nullable=False),
        sa.Column("von_halt_id", sa.Integer(), nullable=False),
        sa.Column("nach_halt_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("final_price", sa.Float(), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="0"),

        sa.ForeignKeyConstraint(
            ["fahrt_id"],
            ["fahrtdurchfuehrung.fahrt_id"],
            ondelete="CASCADE",
            name="fk_fahrt_segment_fahrt",
        ),
        sa.ForeignKeyConstraint(
            ["von_halt_id"],
            ["fahrt_halt.id"],
            ondelete="CASCADE",
            name="fk_fahrt_segment_von_halt",
        ),
        sa.ForeignKeyConstraint(
            ["nach_halt_id"],
            ["fahrt_halt.id"],
            ondelete="CASCADE",
            name="fk_fahrt_segment_nach_halt",
        ),
        sa.UniqueConstraint("fahrt_id", "position", name="uq_fahrt_seg_pos"),
        sa.CheckConstraint("final_price >= 0", name="ck_fahrt_seg_price_nonneg"),
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_dienstzuweisung_fahrt_id;")
    op.execute("DROP TABLE IF EXISTS fahrt_segment;")
    op.execute("DROP TABLE IF EXISTS fahrt_halt;")
    op.execute("DROP TABLE IF EXISTS dienstzuweisung;")