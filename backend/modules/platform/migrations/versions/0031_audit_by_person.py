"""Activity per person (2026-11-18, step 4F): an index on nbpl_audit (company_id, actor, created_at), so one
employee's own entries are read newest first without reading anyone else's. Added in place; no rows change.

Revision ID: 0031
Revises: 0030
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

NAME = "nbpl_audit_actor"


def upgrade() -> None:
    if NAME not in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("nbpl_audit")}:
        op.create_index(NAME, "nbpl_audit", ["company_id", "actor", "created_at"])


def downgrade() -> None:
    op.drop_index(NAME, table_name="nbpl_audit")
