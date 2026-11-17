"""Scorecards (decided 2026-10-22): each division's 100-point monthly scorecard
from its sales playbook, for its reps, coaches or mentor (nbcm_scorecards).
A scorecard names the KPIs it scores, the points each is worth and the bands
that give them, the caps a missed gate puts on the month (IST under 60%: no
more than 40) and the performance bands with their yearly raises. The KPIs
and their monthly targets stay where they are (nbcm_kpis, nbcm_kpi_targets).

Revision ID: 0077
Revises: 0076
"""

from alembic import op
import sqlalchemy as sa

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "nbcm_scorecards" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbcm_scorecards",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(40), nullable=False, unique=True),
            sa.Column("name", sa.String(80), nullable=False, unique=True),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("teams", sa.JSON(), nullable=False),
            sa.Column("roles", sa.JSON(), nullable=False),
            sa.Column("items", sa.JSON(), nullable=False),
            sa.Column("bands", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("nbcm_scorecards")
