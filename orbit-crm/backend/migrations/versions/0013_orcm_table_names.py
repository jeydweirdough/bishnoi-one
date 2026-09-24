"""Every table's name starts with orcm_ (ORbit CRM), so it is plain which app a
table belongs to, whatever database it ends up in. The revision table moves
too (orcm_alembic_version), before this runs: see app/migrate.py.

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

TABLES = (
    "teams",
    "roles",
    "role_permissions",
    "users",
    "sessions",
    "audit_log",
    "customer_types",
    "companies",
    "contacts",
    "activities",
    "price_types",
    "products",
    "product_prices",
    "team_price_types",
    "team_prices",
    "promos",
    "bundles",
    "issuers",
    "sales_settings",
    "quotes",
    "stored_files",
    "form_sections",
    "form_fields",
)


def upgrade() -> None:
    for name in TABLES:
        op.rename_table(name, f"orcm_{name}")


def downgrade() -> None:
    for name in TABLES:
        op.rename_table(f"orcm_{name}", name)
