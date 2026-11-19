"""Order links: a rep gives a customer a link that works once, until it
expires, to pick medicines at their own prices; a quote is made from it.

Revision ID: 0052
Revises: 0051
"""

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_quote_links" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbcm_quote_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("nbcm_contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("price_type", sa.String(40), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("nbcm_users.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quote_id", sa.String(36), sa.ForeignKey("nbcm_quotes.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("nbcm_quote_links")
