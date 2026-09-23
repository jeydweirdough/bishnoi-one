"""a team's own prices

A Team Lead decides which price types their team quotes with and what it
charges. Both tables are sparse on purpose: a team with no rows behaves exactly
as it did before this existed, following its division's price types and the
company's amounts.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_price_types",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("division_code", sa.String(length=32), nullable=False),
        sa.Column("subdivision_code", sa.String(length=40), nullable=False),
        sa.Column("price_type_code", sa.String(length=40), nullable=False),
        sa.Column("set_by_id", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["org_id", "division_code", "subdivision_code"],
            ["subdivisions.org_id", "subdivisions.division_code", "subdivisions.code"],
        ),
        sa.ForeignKeyConstraint(["org_id", "price_type_code"], ["price_types.org_id", "price_types.code"]),
        sa.PrimaryKeyConstraint("org_id", "division_code", "subdivision_code", "price_type_code"),
    )
    op.create_table(
        "team_prices",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("division_code", sa.String(length=32), nullable=False),
        sa.Column("subdivision_code", sa.String(length=40), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("price_type_code", sa.String(length=40), nullable=False),
        sa.Column("amount_centavos", sa.Integer(), nullable=False),
        sa.Column("set_by_id", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_centavos >= 0", name="team_price_not_negative"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["org_id", "division_code", "subdivision_code"],
            ["subdivisions.org_id", "subdivisions.division_code", "subdivisions.code"],
        ),
        sa.ForeignKeyConstraint(["org_id", "product_id"], ["products.org_id", "products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id", "price_type_code"], ["price_types.org_id", "price_types.code"]),
        sa.PrimaryKeyConstraint("org_id", "division_code", "subdivision_code", "product_id", "price_type_code"),
    )


def downgrade() -> None:
    op.drop_table("team_prices")
    op.drop_table("team_price_types")
