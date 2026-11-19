"""One e-signature per person, and the company's letterhead (feature plan step 10, 2026-10-29).

- nbpl_signatures: each person's signature on their account (a PNG, black on transparent), set on
  their profile; a replaced or removed one is kept, for what it signed. Every app asks for the
  current one when someone signs a step (GET /connect/signature).
- On nbpl_companies: the letterhead every printed document carries: legal name, address, TIN,
  phone, logo and a footer.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

LETTERHEAD = (("legal_name", sa.String(200)), ("address", sa.String(400)), ("tin", sa.String(30)), ("phone", sa.String(40)),
              ("logo", sa.LargeBinary()), ("logo_type", sa.String(20)), ("document_footer", sa.String(400)))


def upgrade() -> None:
    bind = op.get_bind()
    if "nbpl_signatures" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbpl_signatures",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("nbpl_accounts.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("image", sa.LargeBinary(), nullable=False),
            sa.Column("method", sa.String(10), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("replaced_at", sa.DateTime(timezone=True)),
        )
    have = {c["name"] for c in sa.inspect(bind).get_columns("nbpl_companies")}
    for name, kind in LETTERHEAD:
        if name not in have:
            op.add_column("nbpl_companies", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbpl_companies") as batch:
        for name, _ in LETTERHEAD:
            batch.drop_column(name)
    op.drop_table("nbpl_signatures")
