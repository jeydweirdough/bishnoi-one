"""A visit as the field agent's one call log (Rx playbook): a visit can be
"detailed" (products presented, no money involved), and says what was done
about the doctor's Patient Care Group; the doctor keeps when they joined one.

Revision ID: 0067
Revises: 0066
"""

from alembic import op
import sqlalchemy as sa

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nbcm_visits") as batch:
        batch.drop_constraint("visit_outcome", type_="check")
        batch.create_check_constraint("visit_outcome", "outcome IN ('detailed', 'collected', 'promised', 'not_in', 'updated', 'other')")
        batch.add_column(sa.Column("care_group", sa.String(12), nullable=True))
    with op.batch_alter_table("nbcm_companies") as batch:
        batch.add_column(sa.Column("care_group_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_companies") as batch:
        batch.drop_column("care_group_at")
    with op.batch_alter_table("nbcm_visits") as batch:
        batch.drop_column("care_group")
        batch.drop_constraint("visit_outcome", type_="check")
        batch.create_check_constraint("visit_outcome", "outcome IN ('collected', 'promised', 'not_in', 'updated', 'other')")
