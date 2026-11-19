"""Activity per person (2026-11-18, step 4F): an index on nbfi_audit_log (actor_id, id), so one employee's own
entries are read newest first without reading anyone else's. Added in place; no rows change.

Revision ID: 0037
Revises: 0036
"""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

NAME = "nbfi_audit_log_actor"


def upgrade() -> None:
    if NAME not in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("nbfi_audit_log")}:
        op.create_index(NAME, "nbfi_audit_log", ["actor_id", "id"])


def downgrade() -> None:
    op.drop_index(NAME, table_name="nbfi_audit_log")
