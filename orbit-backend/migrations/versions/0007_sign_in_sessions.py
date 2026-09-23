"""sign-in sessions and single sign-on: sessions, sso_clients, sso_codes

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('sso_clients',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('secret_hash', sa.String(length=64), nullable=False),
    sa.Column('redirect_uris', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sessions',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('org_id', 'id', name='session_in_company')
    )
    op.create_index(op.f('ix_sessions_org_id'), 'sessions', ['org_id'], unique=False)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('sso_codes',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('client_id', sa.String(length=40), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('redirect_uri', sa.String(length=500), nullable=False),
    sa.Column('code_challenge', sa.String(length=128), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['client_id'], ['sso_clients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id', 'session_id'], ['sessions.org_id', 'sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sso_codes_org_id'), 'sso_codes', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_table('sso_codes')
    op.drop_table('sessions')
    op.drop_table('sso_clients')
