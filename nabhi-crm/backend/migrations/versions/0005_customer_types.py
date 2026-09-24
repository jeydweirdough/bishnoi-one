"""Customer types: the list a company's type ("status") is picked from, kept by
an administrator instead of fixed in code. Starts with the four there were.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

STARTING = (
    ("prospect", "Prospect", "gray", 0),
    ("customer", "Customer", "brand", 1),
    ("partner", "Partner", "green", 2),
    ("inactive", "Inactive", "muted", 3),
)


def upgrade() -> None:
    types = op.create_table(
        "customer_types",
        sa.Column("code", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("color", sa.String(12), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.bulk_insert(types, [{"code": c, "name": n, "color": k, "sort_order": s, "is_active": True} for c, n, k, s in STARTING])
    # A company's type is now whatever is on that list, so the fixed check goes.
    checks = {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints("companies")}
    if "company_status" in checks:
        with op.batch_alter_table("companies") as batch:
            batch.drop_constraint("company_status", type_="check")


def downgrade() -> None:
    op.drop_table("customer_types")
