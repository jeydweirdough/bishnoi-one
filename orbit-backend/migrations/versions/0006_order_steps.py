"""order steps in roles: Orders module grants and the Management, Finance Staff and Dispatch Staff roles

Seeding only adds roles to a company that has none, so every existing company
gets them here. Starting roles an admin still has get their order steps
(grants they already have are left alone); roles an admin deleted aren't
brought back, and the three new roles are only added where the key is free.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

SALES = ("b2c", "stc", "uro", "bnb", "b2b", "hos")
LEAD = ("view", "raise", "edit", "endorse", "send_back", "reject")

# Order steps for the starting roles, where the role still exists.
ORDER_GRANTS = {
    "rep": ("view", "raise"),
    "team_lead": LEAD,
    "division_head": LEAD,
    "executive": ("view",),
    "admin": ("view", "delete", "restore"),
}

NEW_ROLES = (
    (
        "management",
        "Management",
        "Approves, sends back or rejects orders, and sees the sales divisions' figures.",
        {**{k: ("view", "report") for k in SALES}, "orders": ("view", "approve", "send_back", "reject", "edit")},
    ),
    (
        "finance_staff",
        "Finance Staff",
        "Verifies order payments or holds them, and works the Finance desk.",
        {"finance": ("view", "create", "edit"), "orders": ("view", "verify_payment", "hold", "edit")},
    ),
    (
        "dispatch_staff",
        "Dispatch Staff",
        "Picks, packs, dispatches and delivers orders.",
        {"dispatch": ("view", "create", "edit"), "orders": ("view", "fulfil", "deliver")},
    ),
)


def upgrade() -> None:
    bind = op.get_bind()
    meta = sa.MetaData()
    organizations = sa.Table("organizations", meta, autoload_with=bind)
    roles = sa.Table("roles", meta, autoload_with=bind)
    permissions = sa.Table("role_permissions", meta, autoload_with=bind)

    for (org,) in bind.execute(sa.select(organizations.c.id)).all():
        have_roles = {
            key: order
            for key, order in bind.execute(sa.select(roles.c.key, roles.c.sort_order).where(roles.c.org_id == org)).all()
        }
        if not have_roles:
            continue  # seeding gives an empty company every starting role, these included
        granted = {
            (r, m, a)
            for r, m, a in bind.execute(
                sa.select(permissions.c.role_key, permissions.c.module_key, permissions.c.action).where(permissions.c.org_id == org)
            ).all()
        }
        rows = []
        for role, actions in ORDER_GRANTS.items():
            if role in have_roles:
                rows += [{"org_id": org, "role_key": role, "module_key": "orders", "action": a} for a in actions if (role, "orders", a) not in granted]
        next_order = max(have_roles.values(), default=0) + 1
        for key, name, description, grants in NEW_ROLES:
            if key in have_roles:
                continue
            bind.execute(roles.insert().values(org_id=org, key=key, name=name, description=description, sort_order=next_order))
            next_order += 1
            rows += [{"org_id": org, "role_key": key, "module_key": m, "action": a} for m, actions in grants.items() for a in actions]
        if rows:
            bind.execute(permissions.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM role_permissions WHERE module_key = 'orders'"))
    for key, *_ in NEW_ROLES:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE role_key = :k"), {"k": key})
        bind.execute(sa.text("DELETE FROM roles WHERE key = :k AND key NOT IN (SELECT role_key FROM assignments)"), {"k": key})
