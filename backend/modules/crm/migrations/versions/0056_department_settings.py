"""A manager runs their department's settings: its promos and bundles, its
quotation templates and attention rules, its people's targets, and its own
retention windows (two columns on the team; empty is the company's). The
permission is department.manage; the Manager role starts with it.

Revision ID: 0056
Revises: 0055
"""

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("nbcm_teams")}
    with op.batch_alter_table("nbcm_teams") as batch:
        if "at_risk_days" not in columns:
            batch.add_column(sa.Column("at_risk_days", sa.Integer(), nullable=True))
        if "lost_days" not in columns:
            batch.add_column(sa.Column("lost_days", sa.Integer(), nullable=True))
    manager = bind.execute(sa.text("SELECT id FROM nbcm_roles WHERE lower(name) = 'manager' AND is_system = false")).scalar()
    if manager is not None:
        held = bind.execute(
            sa.text("SELECT 1 FROM nbcm_role_permissions WHERE role_id = :id AND permission = 'department.manage'"), {"id": manager}
        ).first()
        if held is None:
            bind.execute(sa.text("INSERT INTO nbcm_role_permissions (role_id, permission) VALUES (:id, 'department.manage')"), {"id": manager})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM nbcm_role_permissions WHERE permission = 'department.manage'"))
    with op.batch_alter_table("nbcm_teams") as batch:
        batch.drop_column("lost_days")
        batch.drop_column("at_risk_days")
