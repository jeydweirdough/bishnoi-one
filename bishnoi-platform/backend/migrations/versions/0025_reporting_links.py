"""Reports to and assistant to (2026-11-03): links between people say whose records a manager reaches. Two nullable
columns, added in place; nobody is linked until a company (or app.tools.reporting_links) does it.

Revision ID: 0025
Revises: 0024
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbpl_identities")}
    for name in ("reports_to_id", "assistant_of_id"):
        if name not in have:
            op.add_column("nbpl_identities", sa.Column(name, sa.String(length=36), nullable=True))
            op.create_index(f"ix_nbpl_identities_{name}", "nbpl_identities", [name])


def downgrade() -> None:
    for name in ("reports_to_id", "assistant_of_id"):
        op.drop_index(f"ix_nbpl_identities_{name}", table_name="nbpl_identities")
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.drop_column("reports_to_id")
        batch.drop_column("assistant_of_id")
