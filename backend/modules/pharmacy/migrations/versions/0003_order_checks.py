"""Orders sent by another Nabhi app for the pharmacist's check: where each
prescription came from (nbph_prescriptions.source, source_id, source_ref,
source_by). Plain added columns and one unique index, so SQLite adds them in
place.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

COLUMNS = (("source", 20), ("source_id", 64), ("source_ref", 40), ("source_by", 120))
INDEX = "uq_nbph_prescriptions_source"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    have = {c["name"] for c in inspector.get_columns("nbph_prescriptions")}
    for name, length in COLUMNS:
        if name not in have:
            op.add_column("nbph_prescriptions", sa.Column(name, sa.String(length), nullable=True))
    # One prescription per order an app sends: sending it again finds it.
    if INDEX not in {i["name"] for i in inspector.get_indexes("nbph_prescriptions")}:
        op.create_index(INDEX, "nbph_prescriptions", ["source", "source_id"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX, table_name="nbph_prescriptions")
    for name, _ in reversed(COLUMNS):
        op.drop_column("nbph_prescriptions", name)
