"""Administration: teams, roles and their permissions, the audit log; every
user gets a role (and may get a team) in place of the old admin/member flag.

The starting roles are written out here, not imported, so changing the
defaults in app/permissions.py later never rewrites what this did.

Revision ID: 0002
Revises: 0001
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CRUD = "view create edit delete"
EVERYTHING = {
    "dashboard": "view", "customers": CRUD, "leads": CRUD, "opportunities": CRUD, "deals": CRUD,
    "activities": CRUD, "products": CRUD, "quotes": CRUD + " approve", "orders": CRUD + " approve",
    "contracts": CRUD, "documents": CRUD, "reports": "view export", "automations": "view manage",
    "integrations": "view manage", "admin": "users roles teams audit",
}
# name, description, scope, {area: actions}
ROLES = (
    ("Administrator", "Everything, including users, roles, teams and the audit log.", "all", EVERYTHING),
    ("Manager", "Sees and works every record, approves quotes and orders, runs reports. No administration.", "all", {
        "dashboard": "view", "customers": CRUD, "leads": CRUD, "opportunities": CRUD, "deals": CRUD,
        "activities": CRUD, "products": "view", "quotes": CRUD + " approve", "orders": CRUD + " approve",
        "contracts": CRUD, "documents": CRUD, "reports": "view export", "automations": "view", "integrations": "view",
    }),
    ("Team Lead", "Works their team's records and runs its reports.", "team", {
        "dashboard": "view", "customers": CRUD, "leads": CRUD, "opportunities": CRUD, "deals": CRUD,
        "activities": CRUD, "products": "view", "quotes": CRUD, "orders": CRUD, "contracts": "view",
        "documents": CRUD, "reports": "view",
    }),
    ("Sales Rep", "Works their own customers, leads, deals and quotes.", "own", {
        "dashboard": "view", "customers": "view create edit", "leads": "view create edit",
        "opportunities": "view create edit", "deals": "view create edit", "activities": "view create edit",
        "products": "view", "quotes": "view create edit", "orders": "view create edit",
        "contracts": "view", "documents": "view",
    }),
)


def upgrade() -> None:
    now = datetime.now(UTC)
    # Created empty: teams are the company's to make.
    op.create_table(
        "teams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    roles = op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("scope", sa.String(8), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("scope IN ('own', 'team', 'all')", name="role_scope"),
    )
    grants = op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission", sa.String(64), primary_key=True),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(254), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(36), nullable=True),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    ids = {name: str(uuid.uuid4()) for name, *_ in ROLES}
    op.bulk_insert(roles, [
        {"id": ids[name], "name": name, "description": desc, "scope": scope, "is_system": name == "Administrator", "created_at": now}
        for name, desc, scope, _ in ROLES
    ])
    op.bulk_insert(grants, [
        {"role_id": ids[name], "permission": f"{area}.{action}"}
        for name, _, _, areas in ROLES
        for area, actions in areas.items()
        for action in actions.split()
    ])

    # Everyone keeps what they had: an admin becomes an Administrator, anyone else a Sales Rep.
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("team_id", sa.String(36), nullable=True))
    users = sa.table("users", sa.column("role", sa.String), sa.column("role_id", sa.String))
    op.execute(users.update().where(users.c.role == "admin").values(role_id=ids["Administrator"]))
    op.execute(users.update().where(users.c.role != "admin").values(role_id=ids["Sales Rep"]))
    # The old admin/member check, where the database has one.
    checks = {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints("users")}
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role_id", existing_type=sa.String(36), nullable=False)
        batch.create_foreign_key("fk_users_role_id", "roles", ["role_id"], ["id"])
        batch.create_foreign_key("fk_users_team_id", "teams", ["team_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_users_role_id", ["role_id"])
        batch.create_index("ix_users_team_id", ["team_id"])
        if "user_role" in checks:
            batch.drop_constraint("user_role", type_="check")
        batch.drop_column("role")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", sa.String(16), nullable=False, server_default="member"))
    op.execute(
        "UPDATE users SET role = 'admin' WHERE role_id IN (SELECT id FROM roles WHERE name = 'Administrator')"
    )
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_team_id")
        batch.drop_index("ix_users_role_id")
        batch.drop_constraint("fk_users_team_id", type_="foreignkey")
        batch.drop_constraint("fk_users_role_id", type_="foreignkey")
        batch.drop_column("team_id")
        batch.drop_column("role_id")
        batch.create_check_constraint("user_role", "role IN ('admin', 'member')")
    op.drop_table("audit_log")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("teams")
