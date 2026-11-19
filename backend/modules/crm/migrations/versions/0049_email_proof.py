"""An email sent from the person's own email app, not through the CRM: it's
logged with a screenshot of it sent, kept as its proof.

Revision ID: 0049
Revises: 0048
"""

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_activities")}
    with op.batch_alter_table("nbcm_activities") as batch:
        if "proof_ref" not in have:
            batch.add_column(sa.Column("proof_ref", sa.String(32), nullable=True))
        if "proof_name" not in have:
            batch.add_column(sa.Column("proof_name", sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_activities") as batch:
        batch.drop_column("proof_name")
        batch.drop_column("proof_ref")
