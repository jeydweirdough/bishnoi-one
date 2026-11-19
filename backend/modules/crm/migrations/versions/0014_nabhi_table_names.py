"""Nabhi: the CRM's tables go from orcm_ (Orbit CRM) to nbcm_ (NaBhi CRM).
The revision table moves too (nbcm_alembic_version), before this runs: see
app/migrate.py.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
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
    _move(TABLES, "nbcm_", ("orcm_", ""))


def downgrade() -> None:
    _move(TABLES, "orcm_", ("nbcm_",))


def _move(tables: tuple[str, ...], target: str, sources: tuple[str, ...]) -> None:
    """Each table to its target name, from whichever older name it has. A
    table already under the target name is left alone, so a database whose
    names ran ahead of its recorded revision (a deploy that stopped partway)
    comes out right all the same."""
    present = set(sa.inspect(op.get_bind()).get_table_names())
    for name in tables:
        if f"{target}{name}" in present:
            continue
        old = next((f"{s}{name}" for s in sources if f"{s}{name}" in present), None)
        if old is not None:
            op.rename_table(old, f"{target}{name}")
