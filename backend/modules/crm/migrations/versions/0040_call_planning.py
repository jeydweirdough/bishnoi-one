"""Planning a call: its objective and the products to bring up; once done,
what came of it and the products actually discussed.

Revision ID: 0040
Revises: 0039
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

ADDED = [
    ("objective", sa.String(300), None),
    ("products", sa.JSON, "'[]'"),
    ("outcome", sa.Text, None),
    ("discussed", sa.JSON, "'[]'"),
]


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_activities")}
    with op.batch_alter_table("nbcm_activities") as batch:
        for name, kind, default in ADDED:
            if name not in have:
                batch.add_column(sa.Column(name, kind, nullable=default is None, server_default=sa.text(default) if default else None))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_activities") as batch:
        for name, _, _ in ADDED:
            batch.drop_column(name)
