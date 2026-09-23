"""retention rules and the reports grant

Adds each division's at-risk and lost thresholds (defaults are filled in by
`python -m app.seed`), and gives the new Reports action to the starting roles
of an existing database (seeding only adds roles to an empty one): Team Leads
and Division Heads in every sales module, and Executives in every sales module.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

SALES = ('b2c', 'stc', 'uro', 'bnb', 'b2b', 'hos')
REPORT_ROLES = ('team_lead', 'division_head', 'executive')


def upgrade() -> None:
    op.create_table('retention_rules',
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('at_risk_days', sa.Integer(), nullable=False),
    sa.Column('lost_days', sa.Integer(), nullable=False),
    sa.CheckConstraint('at_risk_days >= 1 AND lost_days > at_risk_days AND lost_days <= 730', name='retention_days'),
    sa.ForeignKeyConstraint(['division_code'], ['divisions.code'], ),
    sa.PrimaryKeyConstraint('division_code')
    )

    connection = op.get_bind()
    roles = sa.table('roles', sa.column('key', sa.String))
    grants = sa.table(
        'role_permissions', sa.column('role_key', sa.String), sa.column('module_key', sa.String), sa.column('action', sa.String)
    )
    existing = set(connection.execute(sa.select(roles.c.key)).scalars())
    already = set(connection.execute(sa.select(grants.c.role_key).where(grants.c.action == 'report')).scalars())
    rows = [
        {'role_key': role, 'module_key': module, 'action': 'report'}
        for role in REPORT_ROLES
        if role in existing and role not in already
        for module in SALES
    ]
    if rows:
        op.bulk_insert(grants, rows)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE action = 'report'")
    op.drop_table('retention_rules')
