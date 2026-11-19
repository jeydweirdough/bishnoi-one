"""Platform features the owner removed (2026-11-17), with their data:

- one email domain per company: nbpl_companies.email_domain and its unique index
  nbpl_companies_email_domain (migration 0019). Anyone a company's administrators add signs in
  with the email they were given; one email is still one account;
- the app catalogue's switches: nbpl_company_switches (migration 0014). Every company runs
  everything it is subscribed to as one operation; subscriptions (nbpl_company_apps) stay with
  the operators.

The "Ask Bishnoi" assistant kept nothing of its own in the database. Audit entries about these
features (company.updated with emailDomain, catalogue.switched_on/off) stay as history.

In place only: DROP INDEX, then ALTER TABLE ... DROP COLUMN (SQLite 3.35+), never a batch
rebuild, because a SQLite batch rebuild of nbpl_companies would drop the rows pointing at it.

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "nbpl_company_switches" in tables:
        op.drop_table("nbpl_company_switches")
    if "nbpl_companies" in tables:
        if "nbpl_companies_email_domain" in {i["name"] for i in inspector.get_indexes("nbpl_companies")}:
            op.drop_index("nbpl_companies_email_domain", table_name="nbpl_companies")
        if "email_domain" in {c["name"] for c in inspector.get_columns("nbpl_companies")}:
            op.drop_column("nbpl_companies", "email_domain")


def downgrade() -> None:
    raise NotImplementedError("0029 removed the company email domain and the app catalogue switches (2026-11-17); restore from the copy made before it.")
