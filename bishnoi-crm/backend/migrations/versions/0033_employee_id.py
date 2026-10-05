"""A person's employee ID: what a customer transfer asks for.

Revision ID: 0033
Revises: 0032
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_users")}
    if "employee_id" not in columns:
        with op.batch_alter_table("nbcm_users") as batch:
            batch.add_column(sa.Column("employee_id", sa.String(20), nullable=True))
            batch.create_index("ix_nbcm_users_employee_id", ["employee_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("nbcm_users") as batch:
        batch.drop_index("ix_nbcm_users_employee_id")
        batch.drop_column("employee_id")
