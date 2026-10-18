"""Employee IDs are given, not typed: everyone without one gets the next free
EMP- number, oldest first. IDs already held stay as they are (customers are
transferred by them); the column was already unique.

Revision ID: 0057
Revises: 0056
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    held = [r[0] for r in bind.execute(sa.text("SELECT employee_id FROM nbcm_users WHERE employee_id IS NOT NULL"))]
    numbers = [int(m.group(1)) for c in held if (m := re.match(r"^EMP-(\d+)$", c))]
    last = max(numbers, default=0)
    without = [r[0] for r in bind.execute(sa.text("SELECT id FROM nbcm_users WHERE employee_id IS NULL ORDER BY created_at, id"))]
    for n, user_id in enumerate(without, last + 1):
        bind.execute(sa.text("UPDATE nbcm_users SET employee_id = :code WHERE id = :id"), {"code": f"EMP-{n:04d}", "id": user_id})


def downgrade() -> None:
    # The IDs given stay: taking them back would unpick customer transfers made by them.
    pass
