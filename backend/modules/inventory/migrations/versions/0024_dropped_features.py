"""Features the owner dropped (2026-11-17), removed with their data:

- dropshipping (15c, the vendor delivering straight to our customer): nbin_purchase_orders.dropship,
  ship_to_name and ship_to_address, and nbin_sales_orders.dropship. nbin_purchase_orders.sales_order_id
  stays: order-on-demand (15b) still ties its purchase orders to the sales order;
- wave picking (14d, one pick list for several deliveries): nbin_waves and nbin_orders.wave_id.
  Packages and their labels stay.

Sale deliveries (kind "sale") are now made only by approving a sales order; the ones already made stay as
they are, so nothing changes in nbin_orders for that.

Recycle-bin entries of waves go too, and other entries lose any rows or cleared links of what was dropped,
so restoring them still works.

In place, never a batch rebuild: on SQLite rebuilding a table drops the rows pointing at it (order lines,
packages, purchase order and sales order lines). SQLite (3.35+) drops a column natively once its index is
gone; Postgres drops it as usual.

Revision ID: 0024
Revises: 0023
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

COLUMNS = (
    ("nbin_purchase_orders", "dropship"),
    ("nbin_purchase_orders", "ship_to_name"),
    ("nbin_purchase_orders", "ship_to_address"),
    ("nbin_sales_orders", "dropship"),
    ("nbin_orders", "wave_id"),
)
TABLES = ("nbin_waves",)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    have = set(inspector.get_table_names())
    for table, column in COLUMNS:
        if table not in have or column not in {c["name"] for c in inspector.get_columns(table)}:
            continue
        for index in inspector.get_indexes(table):
            if column in index["column_names"]:
                op.drop_index(index["name"], table_name=table)
        op.drop_column(table, column)
    for table in TABLES:
        if table in have:
            op.drop_table(table)
    if "nbin_recycle_bin" in have:
        bind.execute(sa.text("DELETE FROM nbin_recycle_bin WHERE kind = 'waves'"))
        dropped = {(t, c) for t, c in COLUMNS}
        for entry_id, rows, unlinked in bind.execute(sa.text("SELECT id, rows, unlinked FROM nbin_recycle_bin")).all():
            items = json.loads(rows) if isinstance(rows, str) else rows or []
            links = json.loads(unlinked) if isinstance(unlinked, str) else unlinked or []
            kept = [i for i in items if i.get("t") not in TABLES]
            kept_links = [i for i in links if i.get("t") not in TABLES and (i.get("t"), i.get("c")) not in dropped]
            if kept != items or kept_links != links:
                update = sa.text("UPDATE nbin_recycle_bin SET rows = :rows, unlinked = :unlinked WHERE id = :id").bindparams(
                    sa.bindparam("rows", type_=sa.JSON), sa.bindparam("unlinked", type_=sa.JSON))
                bind.execute(update, {"rows": kept, "unlinked": kept_links, "id": entry_id})


def downgrade() -> None:
    raise NotImplementedError("0024 removed dropped features and their data (2026-11-17); restore from the copy made before it.")
