"""HR records on employees (2026-11-18, step 4I): nbpl_identities.hr_details (labelled details: SSS no., Pag-IBIG no.,
PhilHealth no., TIN, any label HR adds) and nbpl_hr_documents (contracts, clearances, background checks). Only the
company's administrators and holders of the "Manage HR records" ability read them. Added in place; no rows change.

Revision ID: 0032
Revises: 0031
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "hr_details" not in {c["name"] for c in inspector.get_columns("nbpl_identities")}:
        op.add_column("nbpl_identities", sa.Column("hr_details", sa.JSON(), nullable=True))
    if "nbpl_hr_documents" not in inspector.get_table_names():
        op.create_table(
            "nbpl_hr_documents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("identity_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("label", sa.String(60), nullable=False),
            sa.Column("file_name", sa.String(200), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("uploaded_by", sa.String(254), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_on", sa.Date(), nullable=True),
        )
        op.create_index("ix_nbpl_hr_documents_identity_id", "nbpl_hr_documents", ["identity_id"])


def downgrade() -> None:
    op.drop_index("ix_nbpl_hr_documents_identity_id", table_name="nbpl_hr_documents")
    op.drop_table("nbpl_hr_documents")
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.drop_column("hr_details")
