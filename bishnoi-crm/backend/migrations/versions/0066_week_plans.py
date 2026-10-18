"""A field agent's week, planned by zone, and their coach's review of it.

Revision ID: 0066
Revises: 0065
"""

from alembic import op
import sqlalchemy as sa

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A database made fresh from the models already has them.
    have = sa.inspect(op.get_bind()).get_table_names()
    if "nbcm_plan_stops" not in have:
        _stops()
    if "nbcm_week_plans" not in have:
        _weeks()


def _stops() -> None:
    op.create_table(
        "nbcm_plan_stops",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("day", sa.String(10), nullable=False, index=True),
        sa.Column("slot", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "company_id", "day", name="plan_stop_once"),
        sa.CheckConstraint("slot IN ('morning', 'midday', 'afternoon')", name="plan_stop_slot"),
    )


def _weeks() -> None:
    op.create_table(
        "nbcm_week_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("week", sa.String(10), nullable=False, index=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", "week", name="week_plan_once"),
    )


def downgrade() -> None:
    op.drop_table("nbcm_week_plans")
    op.drop_table("nbcm_plan_stops")
