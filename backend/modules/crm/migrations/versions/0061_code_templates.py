"""A quotation template can be written as code: HTML with %fields%, kept in its
design (app/quote_code.py). The kind's check takes "code" too.

Revision ID: 0061
Revises: 0060
"""

from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nbcm_quote_templates") as batch:
        batch.drop_constraint("quote_template_kind", type_="check")
        batch.create_check_constraint("quote_template_kind", "kind IN ('form', 'excel', 'code')")


def downgrade() -> None:
    op.execute("UPDATE nbcm_quote_templates SET kind = 'form' WHERE kind = 'code'")
    with op.batch_alter_table("nbcm_quote_templates") as batch:
        batch.drop_constraint("quote_template_kind", type_="check")
        batch.create_check_constraint("quote_template_kind", "kind IN ('form', 'excel')")
