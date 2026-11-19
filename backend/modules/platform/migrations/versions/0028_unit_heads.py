"""Several heads per unit (2026-11-04): who heads a unit is a list, not one person. Every unit's head today becomes its first
head; nothing else changes. One new table.

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbpl_unit_heads" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbpl_unit_heads",
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("nbpl_units.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("identity_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_nbpl_unit_heads_identity_id", "nbpl_unit_heads", ["identity_id"])
    op.execute("INSERT INTO nbpl_unit_heads (unit_id, identity_id) SELECT id, manager_id FROM nbpl_units WHERE manager_id IS NOT NULL")


def downgrade() -> None:
    op.drop_index("ix_nbpl_unit_heads_identity_id", table_name="nbpl_unit_heads")
    op.drop_table("nbpl_unit_heads")
