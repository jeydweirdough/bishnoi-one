"""prices belongs only where there is a price list

The "prices" action was handed to every lead who could already edit, which
reached modules that have no prices to set: BID quotes with notes rather than
from a price list, and Inventory and Orders are not divisions at all. A tick
with no screen behind it is a lie on the roles screen.

What stays is a company's sales divisions, read from the divisions table rather
than a list in here, so a division a company added counts too.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE action = 'prices'
              AND module_key NOT IN (
                  SELECT code FROM divisions
                  WHERE divisions.org_id = role_permissions.org_id AND divisions.kind = 'sales'
              )
            """
        )
    )


def downgrade() -> None:
    # Nothing to put back: these were grants nothing could act on.
    pass
