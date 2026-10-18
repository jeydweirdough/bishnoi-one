"""Each vehicle's, fuel card's, sponsorship's and device issue's history: what
was done to it and by whom (renewed, PMS done, booked, blocked, a note). The
records already here start with where they came from.

Revision ID: 0006
Revises: 0005
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

FROM_SHEET = "Moved in from the JASMINE TASKS workbook"
TABLES = (("nbad_vehicles", "vehicles"), ("nbad_fleet_cards", "fleet-cards"), ("nbad_travel_sponsorships", "travel"), ("nbad_device_issues", "devices"))


def _when(value) -> datetime:
    """A stored time, as SQLite (text) or Postgres (a datetime) gives it back."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now(UTC)


def upgrade() -> None:
    if "nbad_record_events" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "nbad_record_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("record_type", sa.String(20), nullable=False, index=True),
            sa.Column("record_id", sa.String(36), nullable=False, index=True),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("text", sa.String(500), nullable=False),
            sa.Column("by_name", sa.String(140), nullable=True),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
        )
    bind = op.get_bind()
    events = sa.table("nbad_record_events", *(sa.column(c) for c in ("id", "record_type", "record_id", "kind", "text", "by_name", "at")))
    for table, path in TABLES:
        rows = bind.execute(sa.text(f"SELECT id, created_at FROM {table}")).all()
        if rows:
            op.bulk_insert(events, [
                {"id": str(uuid.uuid4()), "record_type": path, "record_id": r.id, "kind": "added", "text": FROM_SHEET, "by_name": None,
                 "at": _when(r.created_at)}
                for r in rows
            ])


def downgrade() -> None:
    op.drop_table("nbad_record_events")
