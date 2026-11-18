"""Field tracking that works offline (2026-11-18, Step 4H): nbcm_visits.client_id and nbcm_photos.client_id, the
phone's own id for something kept while offline, unique per owner (visits) and per taker (photos), so a queued item
sent twice is kept once. Added in place; no rows change.

Revision ID: 0087
Revises: 0086
"""

import sqlalchemy as sa
from alembic import op

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None

COLUMNS = (("nbcm_visits", "ix_nbcm_visits_owner_client", "owner_id"), ("nbcm_photos", "ix_nbcm_photos_taker_client", "taken_by_id"))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table, index, owner in COLUMNS:
        if "client_id" not in {c["name"] for c in inspector.get_columns(table)}:
            op.add_column(table, sa.Column("client_id", sa.String(64), nullable=True))
        if index not in {i["name"] for i in inspector.get_indexes(table)}:
            op.create_index(index, table, [owner, "client_id"], unique=True)


def downgrade() -> None:
    for table, index, _ in COLUMNS:
        op.drop_index(index, table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("client_id")
