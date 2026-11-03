"""The company's number and date format (2026-10-31): kept on the Company profile with its currency and time
zone, and sent to every app in the company pass, so no app keeps its own. One column, added in place.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "locale" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbpl_companies")}:
        op.add_column("nbpl_companies", sa.Column("locale", sa.String(length=10), nullable=False, server_default="en-PH"))


def downgrade() -> None:
    with op.batch_alter_table("nbpl_companies") as batch:
        batch.drop_column("locale")
