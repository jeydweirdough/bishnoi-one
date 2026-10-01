"""Words: a price a Team Lead sets for their team is its special price; a price
a salesperson types on a quote for a client is a requested price, and waits
for the lead's approval. The starting price type called "Special Price" is
the second kind, so it's renamed (unless an admin already renamed it).

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE price_types SET name = 'Requested price' WHERE name = 'Special Price'")


def downgrade() -> None:
    op.execute("UPDATE price_types SET name = 'Special Price' WHERE name = 'Requested price'")
