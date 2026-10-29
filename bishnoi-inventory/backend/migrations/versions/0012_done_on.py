"""The day each stock document was done, in the company's time zone (2026-10-29). Late or on time
compares it with the scheduled date: the time it was done is kept in UTC, and just after midnight in
Manila it is still the day before in UTC, which made a document done late read as on time.

Filled in for what is already done, in Asia/Manila (the company's time zone unless it changed it).
Safe to run twice.

Revision ID: 0012
Revises: 0011
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

DOCUMENTS = ("nbin_receipts", "nbin_orders", "nbin_transfers", "nbin_adjustments", "nbin_counts")
ZONE = ZoneInfo("Asia/Manila")


def _day(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return value.astimezone(ZONE).date()


def upgrade() -> None:
    bind = op.get_bind()
    for table in DOCUMENTS:
        if "done_on" not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, sa.Column("done_on", sa.Date(), nullable=True))
            op.create_index(f"ix_{table}_done_on", table, ["done_on"])
        for row_id, done_at in bind.execute(sa.text(f"select id, done_at from {table} where done_at is not null and done_on is null")).all():
            bind.execute(sa.text(f"update {table} set done_on = :d where id = :id"), {"d": _day(done_at), "id": row_id})


def downgrade() -> None:
    for table in DOCUMENTS:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_done_on")
            batch.drop_column("done_on")
