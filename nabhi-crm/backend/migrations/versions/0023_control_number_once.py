"""A control number is given once per template, even when several PCs print
at the same moment (each Nabhi.exe runs its own API on the same database).

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    names = {u["name"] for u in inspector.get_unique_constraints("nbcm_quote_controls")}
    if "quote_control_number_once" not in names:
        with op.batch_alter_table("nbcm_quote_controls") as batch:
            batch.create_unique_constraint("quote_control_number_once", ["template_id", "number"])


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quote_controls") as batch:
        batch.drop_constraint("quote_control_number_once", type_="unique")
