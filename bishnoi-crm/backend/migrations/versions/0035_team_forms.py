"""Forms and customer types per team: a field or type for only some teams (or
everyone but some), pick-list codes with full names, and fields whose values
must be unique. For the Rx team's own customer form.

Revision ID: 0035
Revises: 0034
"""

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

ADDED = {
    "nbcm_form_fields": [
        ("option_names", sa.JSON, "'{}'"),
        ("unique", sa.Boolean, sa.false()),
        ("only_teams", sa.JSON, "'[]'"),
        ("except_teams", sa.JSON, "'[]'"),
    ],
    "nbcm_customer_types": [
        ("only_teams", sa.JSON, "'[]'"),
        ("except_teams", sa.JSON, "'[]'"),
    ],
}


def upgrade() -> None:
    inspect = sa.inspect(op.get_bind())
    for table, columns in ADDED.items():
        have = {c["name"] for c in inspect.get_columns(table)}
        with op.batch_alter_table(table) as batch:
            for name, kind, default in columns:
                if name not in have:
                    server_default = sa.text(default) if isinstance(default, str) else default
                    batch.add_column(sa.Column(name, kind, nullable=False, server_default=server_default))


def downgrade() -> None:
    for table, columns in ADDED.items():
        with op.batch_alter_table(table) as batch:
            for name, _, _ in columns:
                batch.drop_column(name)
