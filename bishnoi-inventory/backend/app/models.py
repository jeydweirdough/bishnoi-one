"""Inventory's tables. Changes to them go through a migration (migrations/versions).

Every table's name starts with nbin_ (Bishnoi One INventory), so it is plain which
app a table belongs to, whatever database it ends up in.

Accounts here are Inventory's own: nobody signed in here exists in any other
Bishnoi One app.

Quantities are whole units of a product's unit of measure. Money is in minor
units (centavos), as whole numbers, so sums never drift.

How stock is kept:
- `Stock` is one balance: a product, in one location of a warehouse, of one
  batch (or none). `on_hand` is what is physically there; `damaged` is the
  part of it set aside as damaged, so not available.
- Every change to a balance is one `Movement`, written in the same
  transaction by app/stock.py. The movements are the audit trail; nothing
  else changes a balance.
- Reserved and allocated quantities aren't stored: they are read off the open
  orders (confirmed = reserved, picking = allocated), so they can't drift. In
  transit is read off the transfers on their way.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, FetchedValue, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, aliased, column_property, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


# --- accounts and access ---------------------------------------------------------------


class Role(Base):
    __tablename__ = "nbin_roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    # Administrator: always every permission, can't be changed or deleted.
    is_system: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    grants: Mapped[list["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan", lazy="selectin")

    @property
    def permissions(self) -> set[str]:
        return {g.permission for g in self.grants}


class RolePermission(Base):
    __tablename__ = "nbin_role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("nbin_roles.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)

    role: Mapped[Role] = relationship(back_populates="grants")


class User(Base):
    __tablename__ = "nbin_users"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbin_users_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    # Their name in parts, as they keep it on their profile; full_name is made
    # from these (app/routers/profile.py), and is what everything else reads.
    first_name: Mapped[str | None] = mapped_column(String(60), default=None)
    middle_initial: Mapped[str | None] = mapped_column(String(4), default=None)
    last_name: Mapped[str | None] = mapped_column(String(60), default=None)
    suffix: Mapped[str | None] = mapped_column(String(10), default=None)
    gender: Mapped[str | None] = mapped_column(String(8), default=None)
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    birthday: Mapped[date | None] = mapped_column(Date, default=None)
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("nbin_roles.id"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Every session started before this ends (see deps.current_user).
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Their Bishnoi One account on the platform, once they have signed in with it (app/platform_pass.py).
    platform_identity_id: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)

    role: Mapped[Role] = relationship(lazy="joined")


class PlatformPass(Base):
    """A pass from the platform already taken: each one works once. Kept until it would have expired."""

    __tablename__ = "nbin_platform_passes"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SignInSession(Base):
    """One sign-in. The browser holds the token; only its hash is kept here."""

    __tablename__ = "nbin_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbin_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class AuditEntry(Base):
    """The activity log: who changed what, and when. Names the fields that
    changed, never their values. Stock itself is traced by `Movement`."""

    __tablename__ = "nbin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    # Kept as written at the time, so the log still reads after a rename.
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32), default=None)
    target_id: Mapped[str | None] = mapped_column(String(36), default=None)
    target: Mapped[str] = mapped_column(String(200), default="")
    fields: Mapped[list[str]] = mapped_column(JSON, default=list)


class Sequence(Base):
    """The next number of each kind of document, per year: PO-2026-00421."""

    __tablename__ = "nbin_sequences"

    key: Mapped[str] = mapped_column(String(16), primary_key=True)  # "PO-2026"
    last: Mapped[int] = mapped_column(Integer, default=0)


class Stamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# --- the catalogue ---------------------------------------------------------------------


class Category(Stamped, Base):
    """Medical Supplies → Syringes. A category may sit inside another."""

    __tablename__ = "nbin_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_categories.id", ondelete="RESTRICT"), index=True, default=None)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id", lazy="joined", join_depth=3)


class Brand(Stamped, Base):
    __tablename__ = "nbin_brands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Unit(Base):
    """A unit of measure: pc, box, bottle."""

    __tablename__ = "nbin_units"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(default=True)


PRODUCT_TYPES = ("stock", "consumable", "asset", "service")
PRODUCT_STATUSES = ("active", "inactive", "discontinued")


class Product(Stamped, Base):
    __tablename__ = "nbin_products"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint("product_type IN ('stock', 'consumable', 'asset', 'service')", name="product_type"),
        CheckConstraint("status IN ('active', 'inactive', 'discontinued')", name="product_status"),
        Index("nbin_products_no", "no", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_categories.id", ondelete="SET NULL"), index=True, default=None)
    brand_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_brands.id", ondelete="SET NULL"), index=True, default=None)
    product_type: Mapped[str] = mapped_column(String(16), default="stock")
    unit_code: Mapped[str] = mapped_column(ForeignKey("nbin_units.code"), default="pc")
    barcode: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    # The supplier it's usually bought from.
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_suppliers.id", ondelete="SET NULL"), index=True, default=None)
    cost_price: Mapped[int] = mapped_column(Integer, default=0)
    selling_price: Mapped[int] = mapped_column(Integer, default=0)
    # Tax in basis points (1200 = 12%), and whether the prices include it.
    tax_rate_bp: Mapped[int] = mapped_column(Integer, default=0)
    tax_inclusive: Mapped[bool] = mapped_column(default=True)
    min_stock: Mapped[int] = mapped_column(Integer, default=0)
    max_stock: Mapped[int | None] = mapped_column(Integer, default=None)
    # At or below this (across every warehouse) it's time to order more.
    reorder_point: Mapped[int] = mapped_column(Integer, default=0)
    reorder_qty: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    track_batches: Mapped[bool] = mapped_column(default=False)
    track_expiry: Mapped[bool] = mapped_column(default=False)
    track_serials: Mapped[bool] = mapped_column(default=False)
    # Specifications: {"Volume": "3 mL", "Needle": "23G"}.
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    # A variant (3 mL) of a parent product (BD Syringe): the parent groups them.
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_products.id", ondelete="SET NULL"), index=True, default=None)
    variant_label: Mapped[str | None] = mapped_column(String(80), default=None)

    category: Mapped[Category | None] = relationship(lazy="joined")
    brand: Mapped[Brand | None] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")
    supplier: Mapped["Supplier | None"] = relationship(lazy="joined", foreign_keys=[supplier_id])
    parent: Mapped["Product | None"] = relationship(remote_side="Product.id", lazy="select")


class ProductImage(Base):
    """A product's pictures, kept in the database like everything else here."""

    __tablename__ = "nbin_product_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id", ondelete="CASCADE"), index=True)
    content_type: Mapped[str] = mapped_column(String(40))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- suppliers --------------------------------------------------------------------------


class Supplier(Stamped, Base):
    __tablename__ = "nbin_suppliers"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbin_suppliers_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    contact_person: Mapped[str | None] = mapped_column(String(120), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    # More people to talk to: [{"name", "role", "email", "phone"}].
    contacts: Mapped[list[dict]] = mapped_column(JSON, default=list)
    payment_terms: Mapped[str | None] = mapped_column(String(80), default=None)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


class SupplierProduct(Base):
    """What a supplier charges for a product, and their own code for it."""

    __tablename__ = "nbin_supplier_products"

    supplier_id: Mapped[str] = mapped_column(ForeignKey("nbin_suppliers.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id", ondelete="CASCADE"), primary_key=True)
    supplier_sku: Mapped[str | None] = mapped_column(String(40), default=None)
    price: Mapped[int] = mapped_column(Integer, default=0)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    supplier: Mapped[Supplier] = relationship(lazy="joined")
    product: Mapped[Product] = relationship(lazy="joined")


# --- where stock is kept ----------------------------------------------------------------


class Warehouse(Stamped, Base):
    __tablename__ = "nbin_warehouses"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbin_warehouses_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    # Where it is on the map, for drawing transfers as routes. Empty until set or found.
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


class Location(Base):
    """A place within a warehouse: a zone, rack or bin. Every warehouse has a
    default one, where stock goes when nobody says otherwise."""

    __tablename__ = "nbin_locations"
    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="location_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    is_default: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")


class Batch(Base):
    """A lot of one product: PCM-260821, made 21 Aug 2026, expires 21 Aug 2028."""

    __tablename__ = "nbin_batches"
    __table_args__ = (UniqueConstraint("product_id", "batch_no", name="batch_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id", ondelete="CASCADE"), index=True)
    batch_no: Mapped[str] = mapped_column(String(60))
    manufactured_on: Mapped[date | None] = mapped_column(Date, default=None)
    expires_on: Mapped[date | None] = mapped_column(Date, index=True, default=None)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_suppliers.id", ondelete="SET NULL"), default=None)
    # When it first came in: stock aging reads this.
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(lazy="joined")


class Stock(Base):
    """One balance: a product, in a location, of a batch (or none)."""

    __tablename__ = "nbin_stock"
    __table_args__ = (
        UniqueConstraint("product_id", "location_id", "batch_id", name="stock_balance"),
        CheckConstraint("on_hand >= 0", name="stock_on_hand"),
        CheckConstraint("damaged >= 0 AND damaged <= on_hand", name="stock_damaged"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id", ondelete="CASCADE"), index=True)
    # The location's warehouse, kept here too so per-warehouse sums are one query.
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("nbin_locations.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_batches.id", ondelete="CASCADE"), index=True, default=None)
    on_hand: Mapped[int] = mapped_column(Integer, default=0)
    damaged: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    product: Mapped[Product] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")
    batch: Mapped[Batch | None] = relationship(lazy="joined")


SERIAL_STATUSES = ("in_stock", "in_transit", "issued", "written_off")


class Serial(Base):
    """One serial-numbered unit, and where it is now."""

    __tablename__ = "nbin_serials"
    __table_args__ = (UniqueConstraint("product_id", "serial_no", name="serial_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id", ondelete="CASCADE"), index=True)
    serial_no: Mapped[str] = mapped_column(String(80))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_batches.id", ondelete="SET NULL"), default=None)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_locations.id", ondelete="SET NULL"), index=True, default=None)
    status: Mapped[str] = mapped_column(String(16), default="in_stock")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# Every kind of movement, and whether it changes what's on hand.
MOVEMENT_KINDS = (
    "receive",  # stock in, from a supplier
    "issue",  # stock out, on an order
    "transfer_out",
    "transfer_in",
    "adjust",  # a correction: a count, found stock, anything else
    "return_in",  # a customer sent it back
    "return_out",  # sent back to the supplier
    "damage",  # set aside as damaged: still on hand, not available
    "write_off",  # damaged stock thrown away
    "expired",
    "lost",
    "reserve",  # held for an order: on hand doesn't change
    "release",  # the hold let go
)


class Movement(Base):
    """One change to one balance. Written only by app/stock.py."""

    __tablename__ = "nbin_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id", ondelete="CASCADE"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_locations.id", ondelete="SET NULL"), default=None)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_batches.id", ondelete="SET NULL"), default=None)
    # Signed: +500 received, -3 lost, -20 reserved. On hand changes by
    # `on_hand_change`, which is 0 for reserve, release and damage.
    quantity: Mapped[int] = mapped_column(Integer)
    on_hand_change: Mapped[int] = mapped_column(Integer, default=0)
    # What was on hand in that balance afterwards.
    on_hand_after: Mapped[int | None] = mapped_column(Integer, default=None)
    # The unit cost at the time, so valuation of a movement survives a price change.
    unit_cost: Mapped[int] = mapped_column(Integer, default=0)
    # The document behind it: PO-2026-00421, TR-2026-00012...
    reference_type: Mapped[str | None] = mapped_column(String(20), default=None)
    reference_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    reference: Mapped[str | None] = mapped_column(String(40), default=None)
    note: Mapped[str | None] = mapped_column(String(300), default=None)
    serials: Mapped[list[str]] = mapped_column(JSON, default=list)
    user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    # Kept as written at the time, so the trail still reads after a rename.
    user_name: Mapped[str] = mapped_column(String(120), default="")

    product: Mapped[Product] = relationship(lazy="joined")
    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    location: Mapped[Location | None] = relationship(lazy="joined")
    batch: Mapped[Batch | None] = relationship(lazy="joined")


# --- purchasing and receiving -----------------------------------------------------------


PO_STATUSES = ("draft", "ordered", "partial", "received", "cancelled")


class PurchaseOrder(Stamped, Base):
    __tablename__ = "nbin_purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("nbin_suppliers.id"), index=True)
    # Where it's to be delivered.
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    ordered_on: Mapped[date | None] = mapped_column(Date, default=None)
    expected_on: Mapped[date | None] = mapped_column(Date, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    ordered_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)

    supplier: Mapped[Supplier] = relationship(lazy="joined")
    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    ordered_by: Mapped[User | None] = relationship(foreign_keys=[ordered_by_id], lazy="joined")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin", order_by="PurchaseOrderLine.position"
    )


class PurchaseOrderLine(Base):
    __tablename__ = "nbin_purchase_order_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="po_line_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("nbin_purchase_orders.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    received: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[int] = mapped_column(Integer, default=0)

    order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")


class Receipt(Base):
    """One delivery taken in: against a purchase order, or on its own."""

    __tablename__ = "nbin_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_purchase_orders.id", ondelete="SET NULL"), index=True, default=None)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_suppliers.id", ondelete="SET NULL"), index=True, default=None)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("nbin_locations.id"))
    # The supplier's delivery receipt or invoice number.
    delivery_ref: Mapped[str | None] = mapped_column(String(60), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    received_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)

    order: Mapped[PurchaseOrder | None] = relationship(lazy="joined")
    supplier: Mapped[Supplier | None] = relationship(lazy="joined")
    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")
    received_by: Mapped[User | None] = relationship(lazy="joined")
    lines: Mapped[list["ReceiptLine"]] = relationship(back_populates="receipt", cascade="all, delete-orphan", lazy="selectin")


class ReceiptLine(Base):
    __tablename__ = "nbin_receipt_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    receipt_id: Mapped[str] = mapped_column(ForeignKey("nbin_receipts.id", ondelete="CASCADE"), index=True)
    order_line_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_purchase_order_lines.id", ondelete="SET NULL"), default=None)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id"))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_batches.id", ondelete="SET NULL"), default=None)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[int] = mapped_column(Integer, default=0)
    serials: Mapped[list[str]] = mapped_column(JSON, default=list)

    receipt: Mapped[Receipt] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")
    batch: Mapped[Batch | None] = relationship(lazy="joined")


# --- orders and issuance ----------------------------------------------------------------


ORDER_KINDS = ("sale", "internal", "department", "project", "distribution")
# draft → confirmed (reserved) → picking (allocated) → issued; or cancelled.
ORDER_STATUSES = ("draft", "confirmed", "picking", "issued", "cancelled")


class Order(Stamped, Base):
    """Stock going out: a customer order, or an issue to a department or project."""

    __tablename__ = "nbin_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    kind: Mapped[str] = mapped_column(String(16), default="sale")
    # Who it's for: a customer, a department, a project.
    recipient: Mapped[str] = mapped_column(String(160))
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    needed_on: Mapped[date | None] = mapped_column(Date, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    confirmed_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    issued_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, default=None)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    confirmed_by: Mapped[User | None] = relationship(foreign_keys=[confirmed_by_id], lazy="joined")
    issued_by: Mapped[User | None] = relationship(foreign_keys=[issued_by_id], lazy="joined")
    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin", order_by="OrderLine.position"
    )


class OrderLine(Base):
    __tablename__ = "nbin_order_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="order_line_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("nbin_orders.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer, default=0)
    # What went out, batch by batch: [{"batchId", "batchNo", "expiresOn", "locationId", "quantity"}].
    picks: Mapped[list[dict]] = mapped_column(JSON, default=list)
    serials: Mapped[list[str]] = mapped_column(JSON, default=list)

    order: Mapped[Order] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")


# --- transfers --------------------------------------------------------------------------


TRANSFER_STATUSES = ("draft", "requested", "approved", "in_transit", "received", "cancelled")


class Transfer(Stamped, Base):
    __tablename__ = "nbin_transfers"
    __table_args__ = (CheckConstraint("from_warehouse_id <> to_warehouse_id", name="transfer_places"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    from_warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    to_warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    requested_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    dispatched_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    received_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    from_warehouse: Mapped[Warehouse] = relationship(foreign_keys=[from_warehouse_id], lazy="joined")
    to_warehouse: Mapped[Warehouse] = relationship(foreign_keys=[to_warehouse_id], lazy="joined")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    requested_by: Mapped[User | None] = relationship(foreign_keys=[requested_by_id], lazy="joined")
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id], lazy="joined")
    dispatched_by: Mapped[User | None] = relationship(foreign_keys=[dispatched_by_id], lazy="joined")
    received_by: Mapped[User | None] = relationship(foreign_keys=[received_by_id], lazy="joined")
    lines: Mapped[list["TransferLine"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan", lazy="selectin", order_by="TransferLine.position"
    )


class TransferLine(Base):
    __tablename__ = "nbin_transfer_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="transfer_line_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    transfer_id: Mapped[str] = mapped_column(ForeignKey("nbin_transfers.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    # What left the source, batch by batch, so the same batches arrive.
    picks: Mapped[list[dict]] = mapped_column(JSON, default=list)
    serials: Mapped[list[str]] = mapped_column(JSON, default=list)

    transfer: Mapped[Transfer] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")


# --- adjustments and counts -------------------------------------------------------------


# Why stock is adjusted, and the movement each makes.
ADJUSTMENT_REASONS = {
    "count": "adjust",  # physical count differs from the system: either way
    "found": "adjust",  # turned up: adds
    "other": "adjust",  # anything else: either way
    "customer_return": "return_in",  # adds
    "supplier_return": "return_out",  # removes
    "damaged": "damage",  # sets aside as damaged: on hand stays
    "write_off": "write_off",  # throws damaged stock away
    "expired": "expired",  # removes
    "lost": "lost",  # removes
}
ADJUSTMENT_STATUSES = ("pending", "posted", "rejected")


class Adjustment(Stamped, Base):
    """A correction to stock, with its reason. Posted at once by someone who
    may approve adjustments; otherwise waiting for one of them."""

    __tablename__ = "nbin_adjustments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    reason: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    # The count it came from, when it came from one.
    count_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_counts.id", ondelete="SET NULL"), default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    decided_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    decided_by: Mapped[User | None] = relationship(foreign_keys=[decided_by_id], lazy="joined")
    lines: Mapped[list["AdjustmentLine"]] = relationship(
        back_populates="adjustment", cascade="all, delete-orphan", lazy="selectin", order_by="AdjustmentLine.position"
    )


class AdjustmentLine(Base):
    __tablename__ = "nbin_adjustment_lines"
    __table_args__ = (CheckConstraint("quantity <> 0", name="adjustment_line_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    adjustment_id: Mapped[str] = mapped_column(ForeignKey("nbin_adjustments.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id"))
    location_id: Mapped[str] = mapped_column(ForeignKey("nbin_locations.id"))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_batches.id", ondelete="SET NULL"), default=None)
    # Signed: +2 found, -3 missing. Reasons that only add or only remove take
    # the size and give it the sign.
    quantity: Mapped[int] = mapped_column(Integer)
    serials: Mapped[list[str]] = mapped_column(JSON, default=list)

    adjustment: Mapped[Adjustment] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")
    batch: Mapped[Batch | None] = relationship(lazy="joined")


# open (counting) → submitted → approved; or cancelled.
COUNT_STATUSES = ("open", "submitted", "approved", "cancelled")


class Count(Stamped, Base):
    """A physical count of a warehouse. What the system expected is written
    down when it starts; the difference becomes an adjustment on approval."""

    __tablename__ = "nbin_counts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    # Only this category (and those inside it), when set.
    category_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_categories.id", ondelete="SET NULL"), default=None)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    submitted_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    submitted_by: Mapped[User | None] = relationship(foreign_keys=[submitted_by_id], lazy="joined")
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id], lazy="joined")
    lines: Mapped[list["CountLine"]] = relationship(back_populates="count", cascade="all, delete-orphan", lazy="selectin", order_by="CountLine.position")


class CountLine(Base):
    __tablename__ = "nbin_count_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    count_id: Mapped[str] = mapped_column(ForeignKey("nbin_counts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id"))
    location_id: Mapped[str] = mapped_column(ForeignKey("nbin_locations.id"))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_batches.id", ondelete="SET NULL"), default=None)
    expected: Mapped[int] = mapped_column(Integer, default=0)
    # Null until someone has counted it.
    counted: Mapped[int | None] = mapped_column(Integer, default=None)

    count: Mapped[Count] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")
    batch: Mapped[Batch | None] = relationship(lazy="joined")


# How many variants a product has. A product with variants only groups them:
# it holds no stock of its own, so it is never low or out.
_variant = aliased(Product)
Product.variant_count = column_property(
    select(func.count(_variant.id)).where(_variant.parent_id == Product.id).correlate_except(_variant).scalar_subquery()
)


# Numbers on SQLite as records are saved (on Postgres the database gives them).
from app.numbering import numbered  # noqa: E402  (after the models it names)

numbered(User, Product, Supplier, Warehouse)
