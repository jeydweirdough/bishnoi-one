"""API keys for programs (the Orders app's scheduled jobs)

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('api_keys',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=24), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('secret_hash', sa.String(length=64), nullable=False),
    sa.Column('scopes', sa.JSON(), nullable=False),
    sa.Column('created_by_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['profiles.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_keys_org_id'), 'api_keys', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_table('api_keys')
