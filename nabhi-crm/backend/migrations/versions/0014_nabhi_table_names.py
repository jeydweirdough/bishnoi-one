"""Nabhi: the CRM's tables go from orcm_ (Orbit CRM) to nbcm_ (NaBhi CRM).
The revision table moves too (nbcm_alembic_version), before this runs: see
app/migrate.py.

Revision ID: 0014
Revises: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
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
        op.rename_table(f"orcm_{name}", f"nbcm_{name}")


def downgrade() -> None:
    for name in TABLES:
        op.rename_table(f"nbcm_{name}", f"orcm_{name}")
