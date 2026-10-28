"""The document chain (feature plan step 9, 2026-10-28): which document came from which, across every
app (a purchase order and its receipts, a count and its adjustment, a deal and its quotes, an invoice
and the one that replaced it). References only (app, kind, id, number), never a document's data; each
app says when two of its documents (or one of its and another app's) are linked, as the business
event "document.linked".

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbpl_document_links" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbpl_document_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_app", sa.String(40), nullable=False),
        sa.Column("from_kind", sa.String(40), nullable=False),
        sa.Column("from_id", sa.String(36), nullable=False),
        sa.Column("from_number", sa.String(60)),
        sa.Column("to_app", sa.String(40), nullable=False),
        sa.Column("to_kind", sa.String(40), nullable=False),
        sa.Column("to_id", sa.String(36), nullable=False),
        sa.Column("to_number", sa.String(60)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "from_app", "from_kind", "from_id", "to_app", "to_kind", "to_id", name="nbpl_document_link_once"),
    )
    op.create_index("nbpl_document_links_from", "nbpl_document_links", ["company_id", "from_app", "from_kind", "from_id"])
    op.create_index("nbpl_document_links_to", "nbpl_document_links", ["company_id", "to_app", "to_kind", "to_id"])


def downgrade() -> None:
    op.drop_table("nbpl_document_links")
