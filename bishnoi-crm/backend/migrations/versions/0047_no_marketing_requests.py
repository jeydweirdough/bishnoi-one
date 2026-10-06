"""Marketing requests are no longer part of the CRM (2026-10-06): every role
loses funds.view, funds.create and funds.approve.

The requests themselves (nbcm_fund_requests, nbcm_fund_purposes) are left as
they were, unread, so nothing already recorded is lost.

Revision ID: 0047
Revises: 0046
"""

from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM nbcm_role_permissions WHERE permission LIKE 'funds.%'")


def downgrade() -> None:
    pass  # the permissions aren't given back: the screens for them are gone
