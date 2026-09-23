"""goal targets

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('goal_targets',
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('goal', sa.String(length=40), nullable=False),
    sa.Column('target', sa.Integer(), nullable=False),
    sa.CheckConstraint('target >= 0', name='goal_target_not_negative'),
    sa.ForeignKeyConstraint(['division_code'], ['divisions.code'], ),
    sa.PrimaryKeyConstraint('division_code', 'goal')
    )


def downgrade() -> None:
    op.drop_table('goal_targets')
