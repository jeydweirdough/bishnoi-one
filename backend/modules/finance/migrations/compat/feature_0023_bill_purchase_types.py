"""Default existing bill lines to other goods inside their existing JSON field.

No table or column is rebuilt. Existing explicit categories are preserved.
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    db = op.get_bind()
    bills = sa.table("nbfi_bills", sa.column("id", sa.String), sa.column("lines", sa.JSON))
    for bill_id, lines in db.execute(sa.select(bills.c.id, bills.c.lines)).all():
        if any("purchaseType" not in line for line in (lines or [])):
            updated = [dict(line, purchaseType=line.get("purchaseType", "other_goods")) for line in lines]
            db.execute(bills.update().where(bills.c.id == bill_id).values(lines=updated))


def downgrade() -> None:
    # Retain classifications rather than destroy recorded accounting details.
    pass
