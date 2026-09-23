"""accounts, teams, roles and assignments

Revision ID: 0001
Revises: 
"""

from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('divisions',
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('profiles',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('roles',
    sa.Column('key', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('local_credentials',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('password_hash', sa.String(length=100), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('role_permissions',
    sa.Column('role_key', sa.String(length=40), nullable=False),
    sa.Column('module_key', sa.String(length=32), nullable=False),
    sa.Column('action', sa.String(length=16), nullable=False),
    sa.ForeignKeyConstraint(['role_key'], ['roles.key'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('role_key', 'module_key', 'action')
    )
    op.create_table('subdivisions',
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['division_code'], ['divisions.code'], ),
    sa.PrimaryKeyConstraint('division_code', 'code')
    )
    op.create_table('assignments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role_key', sa.String(length=40), nullable=False),
    sa.Column('module_key', sa.String(length=32), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=True),
    sa.Column('subdivision_code', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('subdivision_code IS NULL OR division_code IS NOT NULL', name='subdivision_needs_division'),
    sa.ForeignKeyConstraint(['division_code', 'subdivision_code'], ['subdivisions.division_code', 'subdivisions.code'], ),
    sa.ForeignKeyConstraint(['division_code'], ['divisions.code'], ),
    sa.ForeignKeyConstraint(['role_key'], ['roles.key'], ),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('assignments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assignments_user_id'), ['user_id'], unique=False)

    op.create_table('headquarters',
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('subdivision_code', sa.String(length=40), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['division_code', 'subdivision_code'], ['subdivisions.division_code', 'subdivisions.code'], ),
    sa.PrimaryKeyConstraint('division_code', 'subdivision_code', 'code')
    )


def downgrade() -> None:
    op.drop_table('headquarters')
    with op.batch_alter_table('assignments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assignments_user_id'))

    op.drop_table('assignments')
    op.drop_table('subdivisions')
    op.drop_table('role_permissions')
    op.drop_table('local_credentials')
    op.drop_table('roles')
    op.drop_table('profiles')
    op.drop_table('divisions')
