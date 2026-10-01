"""Roles and permissions, and the activity log, as the other Nabhi apps have.

Finance had two fixed kinds of account, admin and member. Now each account has
a role (nbfi_roles) whose permissions are listed (nbfi_role_permissions), and
every change is written to the activity log (nbfi_audit_log). Everyone keeps
what they could do: an admin gets the Administrator role, a member the
Finance Staff role.

The old role column stays, filled but no longer read: dropping it would mean
rebuilding the users table on SQLite, which every other table points at.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# As in app/permissions.py when this was written. The Administrator holds
# every permission by being the system role, so it needs no rows.
ADMIN_ID = "00000000-0000-4000-8000-00000000f001"
STAFF_ID = "00000000-0000-4000-8000-00000000f002"
AUDITOR_ID = "00000000-0000-4000-8000-00000000f003"
VIEW_ALL = ["dashboard.view", "funds.view", "categories.view", "journal.view", "accounts.view", "tax.view"]
ROLES = [
    (ADMIN_ID, "Administrator", "Everything: the setup (accounts, categories, tax), users, roles and the activity log.", True, []),
    (
        STAFF_ID,
        "Finance Staff",
        "Releases cash advances, reviews liquidations, records refunds and reimbursements, and posts journal entries.",
        False,
        [*VIEW_ALL, "funds.release", "funds.check", "funds.settle", "funds.cancel", "journal.post", "journal.reverse"],
    ),
    (AUDITOR_ID, "Auditor", "Sees everything, including the activity log, and changes nothing.", False, [*VIEW_ALL, "admin.audit"]),
]


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "nbfi_roles" not in tables:
        roles = op.create_table(
            "nbfi_roles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False, unique=True),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        grants = op.create_table(
            "nbfi_role_permissions",
            sa.Column("role_id", sa.String(36), sa.ForeignKey("nbfi_roles.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("permission", sa.String(64), primary_key=True),
        )
        op.bulk_insert(roles, [{"id": i, "name": n, "description": d, "is_system": s} for i, n, d, s, _ in ROLES])
        op.bulk_insert(grants, [{"role_id": i, "permission": p} for i, _, _, _, ps in ROLES for p in ps])
    if "nbfi_audit_log" not in tables:
        op.create_table(
            "nbfi_audit_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("actor_id", sa.String(36), nullable=True, index=True),
            sa.Column("actor", sa.String(254), nullable=False),
            sa.Column("action", sa.String(64), nullable=False, index=True),
            sa.Column("target_type", sa.String(32), nullable=True),
            sa.Column("target_id", sa.String(36), nullable=True),
            sa.Column("target", sa.String(200), nullable=False, server_default=""),
            sa.Column("fields", sa.JSON(), nullable=False),
        )
    # A plain added column: SQLite adds it in place, without rebuilding the table.
    # SQLite can't add the foreign key to an existing table, so it's added only
    # where the database can (Postgres); the app never writes a role that isn't there.
    if "role_id" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbfi_users")}:
        op.add_column("nbfi_users", sa.Column("role_id", sa.String(36), nullable=True))
        op.create_index("ix_nbfi_users_role_id", "nbfi_users", ["role_id"])
        if op.get_bind().dialect.name != "sqlite":
            op.create_foreign_key("fk_nbfi_users_role_id", "nbfi_users", "nbfi_roles", ["role_id"], ["id"])
    op.execute(sa.text("UPDATE nbfi_users SET role_id = :admin WHERE role_id IS NULL AND role = 'admin'").bindparams(admin=ADMIN_ID))
    op.execute(sa.text("UPDATE nbfi_users SET role_id = :staff WHERE role_id IS NULL").bindparams(staff=STAFF_ID))


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_nbfi_users_role_id", "nbfi_users", type_="foreignkey")
    op.drop_index("ix_nbfi_users_role_id", table_name="nbfi_users")
    with op.batch_alter_table("nbfi_users") as batch:
        batch.drop_column("role_id")
    op.drop_table("nbfi_audit_log")
    op.drop_table("nbfi_role_permissions")
    op.drop_table("nbfi_roles")
