"""profile pictures

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('profile_photos',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('content_type', sa.String(length=40), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('profile_photos')
