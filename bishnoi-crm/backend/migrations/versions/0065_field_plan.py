"""A doctor's place in a field agent's plan: their tier and their zone.

From the Rx CHC playbook: every doctor on the list has a tier (1, 2 or 3:
visited 4, 2 or 1 times a month) and, each week, a zone: red (patients ready,
visit in the morning), yellow (lapsed, recover them midday) or green (stable,
an afternoon visit to keep in touch). The agent sets both.

Revision ID: 0065
Revises: 0064
"""

from alembic import op
import sqlalchemy as sa

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nbcm_companies") as batch:
        batch.add_column(sa.Column("field_tier", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("field_zone", sa.String(8), nullable=True))
        batch.add_column(sa.Column("zone_set_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("company_field_tier", "field_tier IS NULL OR field_tier IN (1, 2, 3)")
        batch.create_check_constraint("company_field_zone", "field_zone IS NULL OR field_zone IN ('red', 'yellow', 'green')")


def downgrade() -> None:
    with op.batch_alter_table("nbcm_companies") as batch:
        batch.drop_constraint("company_field_zone", type_="check")
        batch.drop_constraint("company_field_tier", type_="check")
        batch.drop_column("zone_set_at")
        batch.drop_column("field_zone")
        batch.drop_column("field_tier")
