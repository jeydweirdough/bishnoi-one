"""An order link records when the customer agreed to the privacy notice, ordering
through it (a medicine order is sensitive personal information under the Data
Privacy Act; none is taken without the yes).

Revision ID: 0058
Revises: 0057
"""

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "privacy_accepted_at" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_quote_links")}:
        with op.batch_alter_table("nbcm_quote_links") as batch:
            batch.add_column(sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quote_links") as batch:
        batch.drop_column("privacy_accepted_at")
