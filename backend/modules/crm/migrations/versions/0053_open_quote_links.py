"""An order link for someone not a customer yet: no customer on it until they
order; then they become the rep's customer, and the quote is theirs.

Revision ID: 0053
Revises: 0052
"""

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nbcm_quote_links") as batch:
        batch.alter_column("company_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quote_links") as batch:
        batch.alter_column("company_id", existing_type=sa.String(36), nullable=False)
