"""Prices are Finance's: who may see and approve the prices waiting in the CRM.

- prices.view and prices.approve, given to Finance Staff where the role
  already exists; prices.view to the Auditor. The Administrator holds every
  permission already.

Nothing is kept here: the proposals and the quotes live in the CRM, and
Finance's decisions are made there (app/crm.py).

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

STAFF_ID = "00000000-0000-4000-8000-00000000f002"
AUDITOR_ID = "00000000-0000-4000-8000-00000000f003"
GRANTS = {STAFF_ID: ("prices.view", "prices.approve"), AUDITOR_ID: ("prices.view",)}


def upgrade() -> None:
    db = op.get_bind()
    for role, permissions in GRANTS.items():
        if db.execute(sa.text("SELECT id FROM nbfi_roles WHERE id = :r"), {"r": role}).scalar() is None:
            continue
        for p in permissions:
            if db.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = :p"), {"r": role, "p": p}).scalar() is None:
                db.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, :p)"), {"r": role, "p": p})


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission LIKE 'prices.%'"))
