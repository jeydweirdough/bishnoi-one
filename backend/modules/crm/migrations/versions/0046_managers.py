"""Managers, above team leads: a team's manager, a scope that reaches every
team one manages ("managed"), and the Manager role to start from (Team Lead's
permissions, and setting targets).

Revision ID: 0046
Revises: 0045
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "manager_id" not in {c["name"] for c in sa.inspect(bind).get_columns("nbcm_teams")}:
        with op.batch_alter_table("nbcm_teams") as batch:
            batch.add_column(sa.Column("manager_id", sa.String(36), nullable=True))
            batch.create_index("ix_nbcm_teams_manager_id", ["manager_id"])
            batch.create_foreign_key("fk_nbcm_teams_manager", "nbcm_users", ["manager_id"], ["id"], ondelete="SET NULL")
    with op.batch_alter_table("nbcm_roles") as batch:
        batch.drop_constraint("role_scope", type_="check")
        batch.create_check_constraint("role_scope", "scope IN ('own', 'team', 'managed', 'all')")
    if bind.execute(sa.text("SELECT id FROM nbcm_roles WHERE lower(name) = 'manager'")).first() is None:
        lead = bind.execute(sa.text("SELECT id FROM nbcm_roles WHERE name = 'Team Lead'")).scalar()
        permissions = set(bind.execute(sa.text("SELECT permission FROM nbcm_role_permissions WHERE role_id = :id"), {"id": lead}).scalars()) if lead else set()
        permissions |= {"goals.view", "goals.manage"}
        role = str(uuid.uuid4())
        bind.execute(
            sa.text("INSERT INTO nbcm_roles (id, name, description, scope, is_system, created_at) VALUES (:id, 'Manager', :d, 'managed', false, :at)"),
            {"id": role, "d": "Above the team leads: manages every team they're the manager of, and its people. Approves their quotes and sets their targets.", "at": datetime.now(UTC)},
        )
        for p in sorted(permissions):
            bind.execute(sa.text("INSERT INTO nbcm_role_permissions (role_id, permission) VALUES (:id, :p)"), {"id": role, "p": p})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE nbcm_roles SET scope = 'team' WHERE scope = 'managed'"))
    with op.batch_alter_table("nbcm_roles") as batch:
        batch.drop_constraint("role_scope", type_="check")
        batch.create_check_constraint("role_scope", "scope IN ('own', 'team', 'all')")
    with op.batch_alter_table("nbcm_teams") as batch:
        batch.drop_column("manager_id")
