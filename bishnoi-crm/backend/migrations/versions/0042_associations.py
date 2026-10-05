"""Associations: records linked to one another with a label, read both ways;
and an activity on more customers than its own. Starts with the labels a
pharma distributor needs.

Revision ID: 0042
Revises: 0041
"""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None

LABELS = [
    ("works_at", "company", "company", "Works at", "People here", 1),
    ("consultant_at", "company", "company", "Consultant at", "Consultants", 2),
    ("part_of", "company", "company", "Part of", "Members", 3),
    ("buys_through", "company", "company", "Buys through", "Supplies", 4),
    ("decision_maker", "contact", "deal", "Decision maker on", "Decision makers", 5),
    ("influencer", "company", "deal", "Influences", "Influenced by", 6),
]


def upgrade() -> None:
    have = sa.inspect(op.get_bind()).get_table_names()
    if "nbcm_association_labels" not in have:
        labels = op.create_table(
            "nbcm_association_labels",
            sa.Column("code", sa.String(40), primary_key=True),
            sa.Column("from_type", sa.String(10), nullable=False),
            sa.Column("to_type", sa.String(10), nullable=False),
            sa.Column("name", sa.String(60), nullable=False),
            sa.Column("inverse_name", sa.String(60), nullable=False),
            sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        )
        op.bulk_insert(labels, [{"code": c, "from_type": f, "to_type": t, "name": n, "inverse_name": i, "sort_order": o, "is_active": True} for c, f, t, n, i, o in LABELS])
    if "nbcm_associations" not in have:
        op.create_table(
            "nbcm_associations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("label_code", sa.String(40), sa.ForeignKey("nbcm_association_labels.code", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("from_type", sa.String(10), nullable=False),
            sa.Column("from_id", sa.String(36), nullable=False, index=True),
            sa.Column("to_type", sa.String(10), nullable=False),
            sa.Column("to_id", sa.String(36), nullable=False, index=True),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("label_code", "from_id", "to_id", name="association_once"),
        )
    if "nbcm_activity_links" not in have:
        op.create_table(
            "nbcm_activity_links",
            sa.Column("activity_id", sa.String(36), sa.ForeignKey("nbcm_activities.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="CASCADE"), primary_key=True, index=True),
        )


def downgrade() -> None:
    op.drop_table("nbcm_activity_links")
    op.drop_table("nbcm_associations")
    op.drop_table("nbcm_association_labels")
