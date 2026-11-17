"""An assistance application's attachments: the patient's IDs, and the other
documents (the form, the prescription, the indigency certificate...).

Revision ID: 0070
Revises: 0069
"""

from alembic import op
import sqlalchemy as sa

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "attachments" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_assistance")}:
        return  # made fresh from the models
    with op.batch_alter_table("nbcm_assistance") as batch:
        batch.add_column(sa.Column("attachments", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_assistance") as batch:
        batch.drop_column("attachments")
