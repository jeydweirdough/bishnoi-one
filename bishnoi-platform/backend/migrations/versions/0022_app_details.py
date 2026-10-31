"""Each app's own details about a person, kept on the Platform (2026-10-30): the CRM's employee ID, the
pharmacist's licence number, whether Finance's calendar is on for them. Edited in the Admin Console (People,
Change details) and sent to each app with the people it's told about. One column, added in place.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "app_details" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbpl_identities")}:
        op.add_column("nbpl_identities", sa.Column("app_details", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.drop_column("app_details")
