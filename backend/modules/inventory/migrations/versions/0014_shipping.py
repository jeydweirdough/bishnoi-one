"""Shipping with couriers (feature plan step 12, 2026-10-29).

- nbin_couriers: the delivery companies we hand parcels to (LBC, J&T, Lalamove made for every
  company; it adds its own), each with a tracking page address ({number} is the tracking number).
- On nbin_orders (deliveries): how it goes (courier, our own delivery, customer pick-up), the courier,
  tracking number, shipping fee and whether the customer is charged it; the delivery's state once
  issued (out for delivery, delivered, failed) with when it was delivered, why it failed and how many
  tries; and the courier's proof-of-delivery photo beside step 10's signature.

Deliveries already issued are counted as delivered when someone signed for them, else out for delivery.

Revision ID: 0014
Revises: 0013
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

COURIERS = (
    ("LBC", "LBC Express", "https://www.lbcexpress.com/track/?tracking_no={number}", 1),
    ("JNT", "J&T Express", "https://www.jtexpress.ph/trajectoryQuery?bills={number}", 2),
    ("LALAMOVE", "Lalamove", None, 3),
)

COLUMNS = (
    ("delivery_method", sa.String(12)),
    ("courier_id", None),
    ("tracking_number", sa.String(60)),
    ("shipping_fee", sa.Integer()),
    ("fee_charged", sa.Boolean()),
    ("delivery_status", sa.String(12)),
    ("delivered_at", sa.DateTime(timezone=True)),
    ("delivered_on", sa.Date()),
    ("failed_reason", sa.String(300)),
    ("attempts", sa.Integer()),
    ("received_photo", sa.LargeBinary()),
    ("received_photo_type", sa.String(20)),
)


def upgrade() -> None:
    bind = op.get_bind()
    if "nbin_couriers" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbin_couriers",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(20), nullable=False, unique=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("tracking_url", sa.String(300)),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    now = datetime.now(UTC)
    have = {c for (c,) in bind.execute(sa.text("select code from nbin_couriers"))}
    for code, name, url, sort in COURIERS:
        if code not in have:
            bind.execute(sa.text("insert into nbin_couriers (id, code, name, tracking_url, sort_order, is_active, created_at, updated_at) "
                                 "values (:id, :code, :name, :url, :sort, true, :now, :now)"),
                         {"id": str(uuid.uuid4()), "code": code, "name": name, "url": url, "sort": sort, "now": now})

    # In place, never rebuilding nbin_orders: on SQLite a rebuild drops what points at it (its lines).
    cols = {c["name"] for c in sa.inspect(bind).get_columns("nbin_orders")}
    fresh = "delivery_status" not in cols
    for name, kind in COLUMNS:
        if name in cols:
            continue
        if name == "courier_id":
            # SQLite can't add a column with its foreign key in place; it isn't enforced there anyway.
            link = () if bind.dialect.name == "sqlite" else (sa.ForeignKey("nbin_couriers.id", name="nbin_orders_courier", ondelete="SET NULL"),)
            op.add_column("nbin_orders", sa.Column("courier_id", sa.String(36), *link))
        elif name in ("shipping_fee", "attempts"):
            op.add_column("nbin_orders", sa.Column(name, kind, nullable=False, server_default="0"))
        elif name == "fee_charged":
            op.add_column("nbin_orders", sa.Column(name, kind, nullable=False, server_default=sa.false()))
        else:
            op.add_column("nbin_orders", sa.Column(name, kind))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("nbin_orders")}
    if "ix_nbin_orders_courier_id" not in indexes:
        op.create_index("ix_nbin_orders_courier_id", "nbin_orders", ["courier_id"])
    if "ix_nbin_orders_delivery_status" not in indexes:
        op.create_index("ix_nbin_orders_delivery_status", "nbin_orders", ["delivery_status"])
    if fresh:
        bind.execute(sa.text("update nbin_orders set delivery_status = 'delivered', delivered_at = received_signed_at, attempts = 1 "
                             "where status = 'issued' and kind = 'sale' and received_signed_at is not null"))
        bind.execute(sa.text("update nbin_orders set delivery_status = 'out', attempts = 1 "
                             "where status = 'issued' and kind = 'sale' and received_signed_at is null"))


def downgrade() -> None:
    op.drop_index("ix_nbin_orders_delivery_status", "nbin_orders")
    op.drop_index("ix_nbin_orders_courier_id", "nbin_orders")
    with op.batch_alter_table("nbin_orders") as batch:
        for name, _ in reversed(COLUMNS):
            batch.drop_column(name)
    op.drop_table("nbin_couriers")
