"""Revenue targets: what each person is expected to sell in a month, next to
their field goals. A team's target is its people's added up.

Revision ID: 0027
Revises: 0026
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_revenue_targets" in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "nbcm_revenue_targets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("month", sa.String(7), nullable=False, index=True),
        sa.Column("amount_centavos", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "month", name="revenue_target_once"),
    )


def downgrade() -> None:
    op.drop_table("nbcm_revenue_targets")
