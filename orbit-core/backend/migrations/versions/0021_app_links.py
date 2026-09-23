"""the apps a company reaches from Orbit, as data

Where the Orders app lives was an environment variable, which meant adding a
second application later needed a developer and a redeploy — the thing this
platform is meant not to need. It is a row a System Admin edits now, in
Settings -> Apps, and a company can add its own.

The built-in ones keep their permissions in code (app/modules.py: the Orders
app's eighteen steps are real capabilities). Only *which applications this
company has, and where they are* moves here.

ORDERS_APP_URL seeds the first row where it is set, so nothing stops working on
the way past; after this the setting is ignored.

Revision ID: 0021
Revises: 0020
"""

import os

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

# The apps Orbit ships with. Kind.APP in app/modules.py, which is where their
# permissions stay; this is only their name and where they live.
BUILT_IN = [
    ("orders", "Orders", "Raise an order and take it through to delivery.", "orders"),
]


def upgrade() -> None:
    op.create_table(
        "app_links",
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True, nullable=False),
        sa.Column("code", sa.String(32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("url", sa.String(300), nullable=False, server_default=""),
        sa.Column("description", sa.String(200), nullable=False, server_default=""),
        sa.Column("icon", sa.String(40)),
        sa.Column("is_built_in", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    bind = op.get_bind()
    # Whatever ORDERS_APP_URL said becomes the first value, so a company that had
    # it set keeps working without anyone opening Settings.
    from_env = (os.environ.get("ORDERS_APP_URL") or "").strip().rstrip("/")
    rows = []
    for org_id, in bind.execute(sa.text("SELECT id FROM organizations")):
        for order, (code, name, description, icon) in enumerate(BUILT_IN):
            rows.append(
                {
                    "org_id": org_id,
                    "code": code,
                    "name": name,
                    "url": from_env if code == "orders" else "",
                    "description": description,
                    "icon": icon,
                    "is_built_in": True,
                    "is_active": True,
                    "sort_order": order,
                }
            )
    if rows:
        op.bulk_insert(
            sa.table(
                "app_links",
                sa.column("org_id", sa.String), sa.column("code", sa.String), sa.column("name", sa.String),
                sa.column("url", sa.String), sa.column("description", sa.String), sa.column("icon", sa.String),
                sa.column("is_built_in", sa.Boolean), sa.column("is_active", sa.Boolean),
                sa.column("sort_order", sa.Integer),
            ),
            rows,
        )


def downgrade() -> None:
    op.drop_table("app_links")
