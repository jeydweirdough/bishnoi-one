"""One email domain per company (decided 2026-10-29): the company's people sign in with an email at it
(getmeds.ph, bishnoione.ai…), and a domain belongs to one company. Set by the company's administrator
in Company profile; app/email_rules.py checks it when people are added or their email changes.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "email_domain" not in {c["name"] for c in sa.inspect(bind).get_columns("nbpl_companies")}:
        op.add_column("nbpl_companies", sa.Column("email_domain", sa.String(253), nullable=True))
    if "nbpl_companies_email_domain" not in {i["name"] for i in sa.inspect(bind).get_indexes("nbpl_companies")}:
        op.create_index("nbpl_companies_email_domain", "nbpl_companies", ["email_domain"], unique=True)


def downgrade() -> None:
    op.drop_index("nbpl_companies_email_domain", "nbpl_companies")
    with op.batch_alter_table("nbpl_companies") as batch:
        batch.drop_column("email_domain")
