"""One email, one person, whatever their level (2026-10-28): an operator administers every company by
the switch on their account, never by a change to a company's own records.

- The memberships made for operators when they signed in (via_operator) were ticked as the company's
  administrator; they only let the operator in, so they no longer are (accounts.runs_company gives
  operators what they need).
- Memberships a company made itself that an operator's sign-in ticked as administrator (the audit log
  says so: "user.updated" by Bishnoi One "as a Platform Admin") go back to what the company set.

Safe to run twice.

Revision ID: 0017
Revises: 0016
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("update nbpl_identities set is_company_admin = false where via_operator = true"))
    flipped = set()
    for target_id, fields in bind.execute(sa.text(
        "select target_id, fields from nbpl_audit where action = 'user.updated' and actor = 'Bishnoi One' and target_id is not null"
    )):
        names = fields if isinstance(fields, list) else json.loads(fields or "[]")
        if "as a Platform Admin" in names:
            flipped.add(target_id)
    for membership in flipped:
        bind.execute(sa.text("update nbpl_identities set is_company_admin = false where id = :id and via_operator = false"), {"id": membership})


def downgrade() -> None:
    pass  # what an operator's sign-in ticked isn't put back
