"""the Developer Admin role, and the second key to Settings

Settings used to be one switch: a role either managed all of it or none. That
left nowhere to put the person who keeps the company *working* -- the one who
fixes the link to another application, reads the log to find out what happened,
or puts an account back when somebody is locked out. Giving them the one switch
would have handed them the price list and the permission matrix too.

So `settings` gains a second action, `recover`, and a role that holds it:

  manage   runs the company -- every settings screen (System Admin, unchanged)
  recover  the company record, its accounts, its app links and the audit log

A company that has already renamed or deleted its roles keeps what it has: this
only adds the role where its key is free, and never touches an existing one.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

KEY = "developer_admin"
NAME = "Developer Admin"
DESCRIPTION = (
    "Keeps the company working: the applications it reaches, the audit log, the company record and its "
    "accounts. Sees no business rules and no records."
)


def upgrade() -> None:
    bind = op.get_bind()
    roles = sa.table(
        "roles",
        sa.column("org_id", sa.String), sa.column("key", sa.String), sa.column("name", sa.String),
        sa.column("description", sa.String), sa.column("sort_order", sa.Integer),
    )
    permissions = sa.table(
        "role_permissions",
        sa.column("org_id", sa.String), sa.column("role_key", sa.String),
        sa.column("module_key", sa.String), sa.column("action", sa.String),
    )

    new_roles, new_permissions = [], []
    for org_id, in bind.execute(sa.text("SELECT id FROM organizations")):
        taken = bind.execute(
            sa.text("SELECT key FROM roles WHERE org_id = :org AND key = :key"), {"org": org_id, "key": KEY}
        ).first()
        if taken:
            continue
        # Last in the list, beside System Admin: it is the rarest thing to hand out.
        after = bind.execute(
            sa.text("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM roles WHERE org_id = :org"), {"org": org_id}
        ).scalar_one()
        new_roles.append(
            {"org_id": org_id, "key": KEY, "name": NAME, "description": DESCRIPTION, "sort_order": after}
        )
        new_permissions.append({"org_id": org_id, "role_key": KEY, "module_key": "settings", "action": "recover"})

    if new_roles:
        op.bulk_insert(roles, new_roles)
        op.bulk_insert(permissions, new_permissions)


def downgrade() -> None:
    bind = op.get_bind()
    # The permissions go with it: role_permissions cascades from roles, but say
    # it plainly rather than relying on the database to be configured for it.
    bind.execute(
        sa.text("DELETE FROM role_permissions WHERE role_key = :key AND module_key = 'settings'"), {"key": KEY}
    )
    bind.execute(sa.text("DELETE FROM roles WHERE key = :key"), {"key": KEY})
    # Any role a company gave the recovery key to keeps its other permissions
    # and simply loses that one, since the action no longer exists.
    bind.execute(sa.text("DELETE FROM role_permissions WHERE module_key = 'settings' AND action = 'recover'"))
