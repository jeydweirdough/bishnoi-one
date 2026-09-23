"""a company's own fields, and which goals it tracks

Three changes, all the same idea: what a company chooses stops being code.

`order_fields` becomes `custom_fields`, told apart by `subject`, so products and
customers can carry a company's own fields the way orders already could.
Products gain `details` to hold them. `company_goals` says which of the goals
Orbit can work out a company actually tracks — no row means it tracks it, so
nothing changes for a company that never opens the screen.

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "custom_fields" not in tables:
        op.rename_table("order_fields", "custom_fields")
    op.add_column("custom_fields", sa.Column("subject", sa.String(length=16), nullable=False, server_default="order"))

    # The primary key gains `subject`, so a product field and an order field may
    # share a key. SQLite rebuilds the table to do it; nothing points at it.
    fields = sa.Table(
        "custom_fields",
        sa.MetaData(),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True, nullable=False),
        sa.Column("subject", sa.String(16), primary_key=True, nullable=False),
        sa.Column("key", sa.String(40), primary_key=True, nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("required", sa.Boolean, nullable=False),
        sa.Column("options", sa.JSON, nullable=False),
        sa.Column("help", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.CheckConstraint("type IN ('text', 'textarea', 'number', 'date', 'choice')", name="custom_field_type"),
        sa.CheckConstraint("subject IN ('order', 'product', 'customer')", name="custom_field_subject"),
    )
    with op.batch_alter_table("custom_fields", copy_from=fields, recreate="always"):
        pass

    op.add_column("products", sa.Column("details", sa.JSON(), nullable=False, server_default="{}"))

    op.create_table(
        "company_goals",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("goal", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("org_id", "goal"),
    )


def downgrade() -> None:
    op.drop_table("company_goals")
    op.drop_column("products", "details")
    op.drop_column("custom_fields", "subject")
    op.rename_table("custom_fields", "order_fields")
