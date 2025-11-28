from alembic import op
import sqlalchemy as sa

revision = '489c1ee4256b'
down_revision = '0bc4504ce779'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        '_alembic_tmp_abschnitt',
        sa.Column('abschnittId', sa.Integer, primary_key=True, nullable=False),
        sa.Column('spurweite', sa.Float, nullable=False),
        sa.Column('nutzungsentgelt', sa.Float, nullable=False),
        sa.Column('max_geschwindigkeit', sa.Integer, nullable=False),
        sa.Column('startBahnhofId', sa.Integer, nullable=False),
        sa.Column('endBahnhofId', sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(['startBahnhofId'], ['bahnhof.bahnhofId'], name='fk_abschnitt_startBahnhofId'),
        sa.ForeignKeyConstraint(['endBahnhofId'], ['bahnhof.bahnhofId'], name='fk_abschnitt_endBahnhofId'),
        sa.CheckConstraint('startBahnhofId <> endBahnhofId', name='check_start_end_ungleich')
    )

    op.execute(
        '''
        INSERT INTO _alembic_tmp_abschnitt (abschnittId, spurweite, nutzungsentgelt, max_geschwindigkeit, startBahnhofId, endBahnhofId)
        SELECT abschnittId, spurweite, nutzungsentgelt, max_geschwindigkeit, startBahnhof, endBahnhof
        FROM abschnitt
        '''
    )


    op.drop_table('abschnitt')

    op.rename_table('_alembic_tmp_abschnitt', 'abschnitt')


def downgrade():

    op.create_table(
        '_alembic_tmp_abschnitt',
        sa.Column('abschnittId', sa.Integer, primary_key=True, nullable=False),
        sa.Column('spurweite', sa.Float, nullable=False),
        sa.Column('nutzungsentgelt', sa.Float, nullable=False),
        sa.Column('max_geschwindigkeit', sa.Integer, nullable=False),
        sa.Column('startBahnhof', sa.Integer, nullable=False),
        sa.Column('endBahnhof', sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(['startBahnhof'], ['bahnhof.bahnhofId']),
        sa.ForeignKeyConstraint(['endBahnhof'], ['bahnhof.bahnhofId']),
        sa.CheckConstraint('startBahnhof <> endBahnhof')
    )

    op.execute(
        '''
        INSERT INTO _alembic_tmp_abschnitt (abschnittId, spurweite, nutzungsentgelt, max_geschwindigkeit, startBahnhof, endBahnhof)
        SELECT abschnittId, spurweite, nutzungsentgelt, max_geschwindigkeit, startBahnhofId, endBahnhofId
        FROM abschnitt
        '''
    )


    op.drop_table('abschnitt')


    op.rename_table('_alembic_tmp_abschnitt', 'abschnitt')
