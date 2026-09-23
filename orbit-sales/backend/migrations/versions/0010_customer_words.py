"""Company is called Customer where people read it: the record a CRM keeps is
a customer. Only form labels still as they started are renamed; one an admin
renamed stays theirs.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE form_fields SET label = 'Customer' WHERE entity = 'contact' AND key = 'companyId' AND label = 'Company'")
    op.execute("UPDATE form_sections SET title = 'The customer' WHERE entity = 'company' AND title = 'The company'")


def downgrade() -> None:
    op.execute("UPDATE form_fields SET label = 'Company' WHERE entity = 'contact' AND key = 'companyId' AND label = 'Customer'")
    op.execute("UPDATE form_sections SET title = 'The company' WHERE entity = 'company' AND title = 'The customer'")
