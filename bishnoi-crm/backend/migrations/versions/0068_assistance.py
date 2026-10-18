"""Government assistance applications (PAP, Rx playbook) a field agent files for a doctor's patient.

Revision ID: 0068
Revises: 0067
"""

from alembic import op
import sqlalchemy as sa

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_assistance" in sa.inspect(op.get_bind()).get_table_names():
        return  # made fresh from the models
    op.create_table(
        "nbcm_assistance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program", sa.String(8), nullable=False, index=True),
        sa.Column("patient_name", sa.String(120), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("nbcm_products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("submitted_on", sa.String(10), nullable=False, index=True),
        sa.Column("status", sa.String(10), nullable=False, index=True),
        sa.Column("decided_on", sa.String(10), nullable=True, index=True),
        sa.Column("receipt_no", sa.String(60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("nbcm_users.id"), nullable=False, index=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("program IN ('dswd', 'pcso', 'ovp', 'yakap')", name="assistance_program"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'denied')", name="assistance_status"),
    )


def downgrade() -> None:
    op.drop_table("nbcm_assistance")
