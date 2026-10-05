"""Three roles: Administrator, Team Lead, Salesperson.

- Manager goes: whoever had it becomes a Team Lead.
- Team Lead manages its own team: everything a Manager could, within the
  team. It approves the team's quotes (special prices, big discounts,
  guarantee letters and payments), sets its prices, and exports its reports.
- Sales Rep is called Salesperson.

Only the starting roles are touched; a role an admin made is left alone.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# What a Team Lead may do, written out here (not imported) so later changes to
# app/permissions.py never rewrite what this did.
CRUD = ("view", "create", "edit", "delete")
TEAM_LEAD = (
    {f"{a}.{x}" for a in ("customers", "leads", "opportunities", "deals", "activities", "quotes", "orders", "contracts", "documents") for x in CRUD}
    | {"quotes.approve", "orders.approve", "dashboard.view", "products.view", "products.prices", "reports.view", "reports.export"}
    | {"automations.view", "integrations.view"}
)


def upgrade() -> None:
    db = op.get_bind()
    role = lambda name: db.execute(sa.text("SELECT id FROM roles WHERE name = :n AND is_system = false"), {"n": name}).scalar()  # noqa: E731
    lead, manager = role("Team Lead"), role("Manager")
    if lead:
        db.execute(
            sa.text("UPDATE roles SET description = :d WHERE id = :id"),
            {"id": lead, "d": "Manages their own team: its customers, quotes and prices. Approves the team's quotes."},
        )
        have = set(db.execute(sa.text("SELECT permission FROM role_permissions WHERE role_id = :id"), {"id": lead}).scalars())
        for permission in sorted(TEAM_LEAD - have):
            db.execute(sa.text("INSERT INTO role_permissions (role_id, permission) VALUES (:id, :p)"), {"id": lead, "p": permission})
    if manager and lead:
        db.execute(sa.text("UPDATE users SET role_id = :lead WHERE role_id = :manager"), {"lead": lead, "manager": manager})
        db.execute(sa.text("DELETE FROM role_permissions WHERE role_id = :id"), {"id": manager})
        db.execute(sa.text("DELETE FROM roles WHERE id = :id"), {"id": manager})
    rep = role("Sales Rep")
    if rep and not role("Salesperson"):
        db.execute(
            sa.text("UPDATE roles SET name = 'Salesperson', description = :d WHERE id = :id"),
            {"id": rep, "d": "Works their own customers, activities and quotes."},
        )


def downgrade() -> None:
    # The name only: who was a Manager before isn't kept, so that part can't be undone.
    op.execute("UPDATE roles SET name = 'Sales Rep' WHERE name = 'Salesperson' AND is_system = false")
