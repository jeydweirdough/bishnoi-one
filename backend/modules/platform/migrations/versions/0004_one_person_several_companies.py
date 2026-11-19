"""One person, several companies: an email is unique within a company, not
across the platform. Each company's row is the person's standing there (their
title, whether they run it, their applications); one password serves them all.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# SQLite keeps an inline UNIQUE without a name: this one names it, so it can be dropped.
NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _email_unique(bind) -> str | None:
    for u in sa.inspect(bind).get_unique_constraints("nbpl_identities"):
        if u["column_names"] == ["email"]:
            return u["name"] or "uq_nbpl_identities_email"
    return None


def upgrade() -> None:
    bind = op.get_bind()
    old = _email_unique(bind)
    with op.batch_alter_table("nbpl_identities", naming_convention=NAMING) as batch:
        if old:
            batch.drop_constraint(old, type_="unique")
        batch.create_unique_constraint("nbpl_identity_email", ["company_id", "email"])
    op.create_index("ix_nbpl_identities_email", "nbpl_identities", ["email"])


def downgrade() -> None:
    op.drop_index("ix_nbpl_identities_email", "nbpl_identities")
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.drop_constraint("nbpl_identity_email", type_="unique")
        batch.create_unique_constraint("nbpl_identities_email_key", ["email"])
