"""One document header on every stock document (feature plan step 8, 2026-10-28).

- nbin_operation_types, with one of each kind made for the company: Receipts, Deliveries, Issues,
  Internal transfers, Adjustments, Counts, Returns.
- On receipts, orders, transfers, adjustments and counts: operation type, scheduled date, done date,
  source document and responsible person. Filled in for what is already there from what each
  document already says (a receipt's purchase order and expected date, an order's needed-by date,
  when each was done, who made it).

Added in place; safe to run twice.

Revision ID: 0010
Revises: 0009
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

DEFAULTS = (
    ("IN", "Receipts", "receipt"),
    ("OUT", "Deliveries", "delivery"),
    ("ISS", "Issues to departments and projects", "issue"),
    ("INT", "Internal transfers", "internal"),
    ("ADJ", "Adjustments", "adjustment"),
    ("CNT", "Counts", "count"),
    ("RET", "Returns", "return"),
)
DOCUMENTS = ("nbin_receipts", "nbin_orders", "nbin_transfers", "nbin_adjustments", "nbin_counts")


def upgrade() -> None:
    bind = op.get_bind()
    inspect = sa.inspect(bind)
    if "nbin_operation_types" not in inspect.get_table_names():
        op.create_table(
            "nbin_operation_types",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(20), nullable=False, unique=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False, index=True),
            sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("nbin_warehouses.id", ondelete="CASCADE")),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("kind IN ('receipt', 'delivery', 'issue', 'internal', 'adjustment', 'count', 'return')", name="operation_kind"),
        )
    now = datetime.now(UTC)
    ids: dict[str, str] = {k: i for i, k in bind.execute(sa.text("select id, kind from nbin_operation_types where is_default = true"))}
    for code, name, kind in DEFAULTS:
        if kind not in ids:
            ids[kind] = str(uuid.uuid4())
            bind.execute(sa.text("insert into nbin_operation_types (id, code, name, kind, is_default, is_active, created_at, updated_at) "
                                 "values (:id, :code, :name, :kind, true, true, :now, :now)"), {"id": ids[kind], "code": code, "name": name, "kind": kind, "now": now})

    for table in DOCUMENTS:
        have = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if "operation_type_id" in have:
            continue
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("operation_type_id", sa.String(36), sa.ForeignKey("nbin_operation_types.id", name=f"{table}_operation_type", ondelete="SET NULL")))
            batch.add_column(sa.Column("scheduled_on", sa.Date()))
            batch.add_column(sa.Column("done_at", sa.DateTime(timezone=True)))
            batch.add_column(sa.Column("source_document", sa.String(80)))
            batch.add_column(sa.Column("responsible_id", sa.String(36), sa.ForeignKey("nbin_users.id", name=f"{table}_responsible", ondelete="SET NULL")))
        for column in ("operation_type_id", "scheduled_on", "done_at", "responsible_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])

    # What is already there, from what each document already says.
    run = lambda sql, **p: bind.execute(sa.text(sql), p)  # noqa: E731
    run("update nbin_receipts set operation_type_id = :t where operation_type_id is null", t=ids["receipt"])
    run("update nbin_receipts set done_at = received_at, responsible_id = received_by_id where done_at is null")
    run("update nbin_receipts set source_document = (select number from nbin_purchase_orders po where po.id = nbin_receipts.order_id), "
        "scheduled_on = (select expected_on from nbin_purchase_orders po where po.id = nbin_receipts.order_id) where order_id is not null and source_document is null")
    run("update nbin_orders set operation_type_id = :t where operation_type_id is null and kind = 'sale'", t=ids["delivery"])
    run("update nbin_orders set operation_type_id = :t where operation_type_id is null", t=ids["issue"])
    run("update nbin_orders set scheduled_on = needed_on, done_at = issued_at, responsible_id = created_by_id where responsible_id is null")
    run("update nbin_transfers set operation_type_id = :t where operation_type_id is null", t=ids["internal"])
    run("update nbin_transfers set done_at = received_at, responsible_id = created_by_id where responsible_id is null")
    run("update nbin_adjustments set operation_type_id = :t where operation_type_id is null", t=ids["adjustment"])
    run("update nbin_adjustments set done_at = decided_at where status = 'posted' and done_at is null")
    run("update nbin_adjustments set responsible_id = created_by_id where responsible_id is null")
    run("update nbin_adjustments set source_document = (select number from nbin_counts c where c.id = nbin_adjustments.count_id) where count_id is not null and source_document is null")
    run("update nbin_counts set operation_type_id = :t where operation_type_id is null", t=ids["count"])
    run("update nbin_counts set done_at = approved_at, responsible_id = created_by_id where responsible_id is null")


def downgrade() -> None:
    for table in DOCUMENTS:
        with op.batch_alter_table(table) as batch:
            for column in ("operation_type_id", "scheduled_on", "done_at", "responsible_id"):
                batch.drop_index(f"ix_{table}_{column}")
            for column in ("responsible_id", "source_document", "done_at", "scheduled_on", "operation_type_id"):
                batch.drop_column(column)
    op.drop_table("nbin_operation_types")
