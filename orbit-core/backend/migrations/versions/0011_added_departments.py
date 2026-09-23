"""departments admins add themselves

Divisions stop being a mirror of app/modules.py: they carry their own kind,
icon and on/off switch, so a company can add a department without a deployment.
The existing rows keep their kind from the module list.

Adding columns is the one thing SQLite does without rebuilding a table, which
matters here: four tables point at `divisions`, so a batch rebuild would drop
those foreign keys on the floor. The CHECK on `kind` needs a rebuild, so it is
made on Postgres and left to the model's own definition on SQLite.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

SALES = ("b2c", "stc", "uro", "bnb", "b2b", "hos")


def upgrade() -> None:
    op.add_column("divisions", sa.Column("kind", sa.String(length=16), nullable=False, server_default="department"))
    op.add_column("divisions", sa.Column("icon", sa.String(length=40), nullable=True))
    op.add_column("divisions", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    divisions = sa.table("divisions", sa.column("code", sa.String), sa.column("kind", sa.String))
    op.execute(divisions.update().where(divisions.c.code.in_(SALES)).values(kind="sales"))

    if op.get_bind().dialect.name != "sqlite":
        op.create_check_constraint("division_kind", "divisions", "kind IN ('sales', 'department')")


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("division_kind", "divisions", type_="check")
    op.drop_column("divisions", "is_active")
    op.drop_column("divisions", "icon")
    op.drop_column("divisions", "kind")
