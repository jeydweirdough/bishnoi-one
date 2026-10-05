"""The pharmacist's check on a quote marked Rx, from Nabhi Pharmacy: what was
sent, Pharmacy's last answer, when it was asked, and why a try failed.
Plain added columns, so SQLite adds them in place.

Revision ID: 0025
Revises: 0024
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

COLUMNS = (
    ("pharmacy_sent", sa.JSON()),
    ("pharmacy_check", sa.JSON()),
    ("pharmacy_synced_at", sa.DateTime(timezone=True)),
    ("pharmacy_error", sa.String(300)),
)


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_quotes")}
    for name, kind in COLUMNS:
        if name not in have:
            op.add_column("nbcm_quotes", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quotes") as batch:
        for name, _ in reversed(COLUMNS):
            batch.drop_column(name)
