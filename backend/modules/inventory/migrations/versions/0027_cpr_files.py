"""CPR files as proof (2026-11-18, owner's Step 2): nbin_product_documents.tag ("cpr" for the item's FDA
registration certificate), indexed for the FDA inspection list. Documents already named with "CPR" are tagged.
Added in place.

Revision ID: 0027
Revises: 0026
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nbin_product_documents", sa.Column("tag", sa.String(20), nullable=True))
    op.create_index("ix_nbin_product_documents_tag", "nbin_product_documents", ["tag"])
    docs = sa.table("nbin_product_documents", sa.column("name", sa.String), sa.column("file_name", sa.String), sa.column("tag", sa.String))
    op.get_bind().execute(docs.update().where(sa.or_(sa.func.upper(docs.c.name).contains("CPR"), sa.func.upper(docs.c.file_name).contains("CPR"))).values(tag="cpr"))


def downgrade() -> None:
    op.drop_index("ix_nbin_product_documents_tag", "nbin_product_documents")
    op.drop_column("nbin_product_documents", "tag")
