"""Form fields by customer type: a field asked only of some kinds of customer
(a doctor's professional profile), or of all but some.

Revision ID: 0036
Revises: 0035
"""

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

COLUMNS = ("only_types", "except_types")


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_form_fields")}
    with op.batch_alter_table("nbcm_form_fields") as batch:
        for name in COLUMNS:
            if name not in have:
                batch.add_column(sa.Column(name, sa.JSON, nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_form_fields") as batch:
        for name in COLUMNS:
            batch.drop_column(name)
