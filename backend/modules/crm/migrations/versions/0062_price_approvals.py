"""Price approvals: prices curated by finance, with doctor's, patient's,
and special prices set by managers requiring finance approval before
becoming visible to salespersons.

Revision ID: 0062
Revises: 0061
"""

from alembic import op
import sqlalchemy as sa

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nbcm_product_prices") as batch:
        batch.add_column(sa.Column("approval_status", sa.String(20), server_default="approved", nullable=False))
        batch.add_column(sa.Column("proposed_amount_centavos", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("submitted_by_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("approved_by_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("rejection_reason", sa.String(500), nullable=True))

    with op.batch_alter_table("nbcm_team_prices") as batch:
        batch.add_column(sa.Column("approval_status", sa.String(20), server_default="approved", nullable=False))
        batch.add_column(sa.Column("proposed_amount_centavos", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("submitted_by_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("approved_by_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("rejection_reason", sa.String(500), nullable=True))

    # Existing prices are set to 'approved'
    op.execute("UPDATE nbcm_product_prices SET approval_status = 'approved' WHERE approval_status IS NULL")
    op.execute("UPDATE nbcm_team_prices SET approval_status = 'approved' WHERE approval_status IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("nbcm_team_prices") as batch:
        batch.drop_column("rejection_reason")
        batch.drop_column("approved_at")
        batch.drop_column("approved_by_id")
        batch.drop_column("submitted_at")
        batch.drop_column("submitted_by_id")
        batch.drop_column("proposed_amount_centavos")
        batch.drop_column("approval_status")

    with op.batch_alter_table("nbcm_product_prices") as batch:
        batch.drop_column("rejection_reason")
        batch.drop_column("approved_at")
        batch.drop_column("approved_by_id")
        batch.drop_column("submitted_at")
        batch.drop_column("submitted_by_id")
        batch.drop_column("proposed_amount_centavos")
        batch.drop_column("approval_status")
