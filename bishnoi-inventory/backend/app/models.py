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

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, FetchedValue, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, false as sa_false, func, select, true as sa_true
from sqlalchemy.orm import Mapped, aliased, column_property, declared_attr, mapped_column, relationship

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


# --- one document header (feature plan step 8, 2026-10-28) ------------------------------
# Every stock document (receipt, sales order or issue, transfer, adjustment, count) says the same few
# things in the same place: what kind of operation it is, when it is scheduled, when it was done,
# the document it came from, and who is responsible (app/documents.py).

OPERATION_KINDS = ("receipt", "delivery", "issue", "internal", "adjustment", "count", "return")


class OperationType(Stamped, Base):
    """A kind of stock operation, as the company names it ("Receipts", "Returns from customers"),
    optionally for one warehouse. One of each kind is made for every company; it adds its own."""

    __tablename__ = "nbin_operation_types"
    __table_args__ = (CheckConstraint("kind IN ('receipt', 'delivery', 'issue', 'internal', 'adjustment', 'count', 'return')", name="operation_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16), index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_warehouses.id", ondelete="CASCADE"), default=None)
    # The one a new document of its kind gets when none is chosen.
    is_default: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)


class Courier(Stamped, Base):
    """A delivery company we hand parcels to (step 12): LBC, J&T and Lalamove for every company; it adds its own.
    `tracking_url` opens the courier's tracking page, with {number} for the tracking number."""

    __tablename__ = "nbin_couriers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    tracking_url: Mapped[str | None] = mapped_column(String(300), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


# How a delivery goes, and where it is once issued (step 12).
DELIVERY_METHODS = ("courier", "own", "pickup")
DELIVERY_STATES = ("out", "delivered", "failed")


class DocumentHeader:
    """The header's columns, on every stock document."""

    @declared_attr
    def operation_type_id(cls) -> Mapped[str | None]:
        return mapped_column(ForeignKey("nbin_operation_types.id", ondelete="SET NULL"), index=True, default=None)

    scheduled_on: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    # The day it was done in the company's time zone (migration 0012): what late or on time compares.
    done_on: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    # The document it came from, by its number: the purchase order behind a receipt, the count behind
    # an adjustment, a customer's PO behind a sale.
    source_document: Mapped[str | None] = mapped_column(String(80), default=None)

    @declared_attr
    def responsible_id(cls) -> Mapped[str | None]:
        return mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None, index=True)

    @declared_attr
    def operation_type(cls) -> Mapped[OperationType | None]:
        return relationship(OperationType, lazy="joined")

    @declared_attr
    def responsible(cls) -> Mapped["User | None"]:
        return relationship("User", foreign_keys=lambda: [cls.responsible_id], lazy="joined")


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
    # Its Certificate of Product Registration from the FDA, and the day it's valid until (app/cpr.py).
    cpr_number: Mapped[str | None] = mapped_column(String(40), index=True, default=None)
    cpr_valid_until: Mapped[date | None] = mapped_column(Date, default=None)

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
    # Its tax registration, for Finance's bills and the BIR's purchase lists: TIN ("123-456-789-00000"),
    # VAT-registered or not ("vat", "non_vat"), and the ATC usually withheld from its payments ("WC158").
    tin: Mapped[str | None] = mapped_column(String(20), default=None)
    vat_status: Mapped[str] = mapped_column(String(8), default="vat")
    default_atc: Mapped[str | None] = mapped_column(String(8), default=None)
    # What it bills in: PHP, or USD for the suppliers abroad (migration 0008).
    currency: Mapped[str] = mapped_column(String(3), default="PHP")


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
    # Checks what it receives before it can be used: receive → check → store (step 14a, migration 0016).
    quality_check: Mapped[bool] = mapped_column(default=False, server_default=sa_false())


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
    # A vendor's consignment stock: theirs until it sells (15d).
    consignment_supplier_id: Mapped[str | None] = mapped_column(String(36), default=None)

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
    # Received and waiting for its quality check (step 14a): on hand, but not available to reserve or pick.
    on_hold: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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
    # Made by replenishment, by hand from its page or at night (step 15a, migration 0020).
    replenishment: Mapped[bool] = mapped_column(default=False, server_default=sa_false())
    # Raised for a sales order (order-on-demand, 15b; dropshipping, 15c), and shipped straight to that customer.
    sales_order_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    dropship: Mapped[bool] = mapped_column(default=False, server_default=sa_false())
    ship_to_name: Mapped[str | None] = mapped_column(String(200), default=None)
    ship_to_address: Mapped[str | None] = mapped_column(String(400), default=None)

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


class Receipt(DocumentHeader, Base):
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
    # Received on consignment: the vendor's until it sells (15d).
    consignment: Mapped[bool] = mapped_column(default=False, server_default=sa_false())
    received_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)

    order: Mapped[PurchaseOrder | None] = relationship(lazy="joined")
    supplier: Mapped[Supplier | None] = relationship(lazy="joined")
    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")
    received_by: Mapped[User | None] = relationship(foreign_keys=[received_by_id], lazy="joined")
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


# --- the Sales app (feature plan step 11, 2026-10-29) --------------------------------------

SALES_ORDER_STATUSES = ("draft", "pending", "confirmed", "delivered", "rejected", "cancelled")


class SalesOrder(Stamped, Base):
    """A customer's order (app/sales.py): made from an approved CRM quote, or typed in the Sales app at the
    price list's prices; waits for approval, then confirmed (which makes its delivery), delivered or cancelled."""

    __tablename__ = "nbin_sales_orders"
    __table_args__ = (CheckConstraint("status IN ('draft', 'pending', 'confirmed', 'delivered', 'rejected', 'cancelled')", name="sales_order_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    # The customer as the CRM has them (the CRM owns customers), as they were when ordered.
    customer_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_address: Mapped[str | None] = mapped_column(String(400), default=None)
    customer_tin: Mapped[str | None] = mapped_column(String(30), default=None)
    # The CRM quote it came from; ordered once.
    quote_id: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)
    quote_number: Mapped[str | None] = mapped_column(String(30), default=None)
    salesperson_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    salesperson_name: Mapped[str | None] = mapped_column(String(120), default=None)
    division_id: Mapped[str | None] = mapped_column(String(36), default=None)
    division_name: Mapped[str | None] = mapped_column(String(120), default=None)
    team_id: Mapped[str | None] = mapped_column(String(36), default=None)
    team_name: Mapped[str | None] = mapped_column(String(120), default=None)
    # {"kind": "customer"} or {"kind": "guarantee_letter", "issuer", "letterNumber", "amountCentavos"}.
    payer: Mapped[dict | None] = mapped_column(JSON, default=None)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    scheduled_on: Mapped[date | None] = mapped_column(Date, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    gross_centavos: Mapped[int] = mapped_column(Integer, default=0)
    discount_centavos: Mapped[int] = mapped_column(Integer, default=0)
    total_centavos: Mapped[int] = mapped_column(Integer, default=0)
    tax: Mapped[dict | None] = mapped_column(JSON, default=None)
    currency: Mapped[str] = mapped_column(String(3), default="PHP")
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    created_by_name: Mapped[str | None] = mapped_column(String(120), default=None)
    decided_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(500), default=None)
    # The vendor ships it straight to the customer (15c).
    dropship: Mapped[bool] = mapped_column(default=False, server_default=sa_false())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # The invoice Finance made from its delivery, and when it was paid in full (step 13, migration 0015).
    invoice_id: Mapped[str | None] = mapped_column(String(36), default=None)
    invoice_number: Mapped[str | None] = mapped_column(String(30), default=None)
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    invoice_total: Mapped[int | None] = mapped_column(Integer, default=None)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    warehouse: Mapped["Warehouse"] = relationship(lazy="joined")
    decided_by: Mapped["User | None"] = relationship(foreign_keys=[decided_by_id], lazy="joined")
    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin", order_by="SalesOrderLine.position"
    )


class SalesOrderLine(Base):
    __tablename__ = "nbin_sales_order_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="sales_order_line_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("nbin_sales_orders.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    free_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[int] = mapped_column(Integer, default=0)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    delivered: Mapped[int] = mapped_column(Integer, default=0)
    # The product's VAT category as the CRM gave it, for the invoice (step 13).
    vat_category: Mapped[str] = mapped_column(String(20), default="standard", server_default="standard")

    order: Mapped[SalesOrder] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship(lazy="joined")


ORDER_KINDS = ("sale", "internal", "department", "project", "distribution")
# draft → confirmed (reserved) → picking (allocated) → issued; or cancelled.
ORDER_STATUSES = ("draft", "confirmed", "picking", "issued", "cancelled")


class Order(DocumentHeader, Stamped, Base):
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
    # Proof of delivery (step 10, migration 0011): who received it, their signature, when, and a
    # fingerprint (SHA-256) of the order as it was signed for.
    received_by_name: Mapped[str | None] = mapped_column(String(120), default=None)
    received_signature: Mapped[bytes | None] = mapped_column(LargeBinary, default=None, deferred=True)
    received_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    received_fingerprint: Mapped[str | None] = mapped_column(String(64), default=None)
    # The sales order it delivers (step 11); none for an issue to a department or project.
    sales_order_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_sales_orders.id", ondelete="SET NULL"), default=None, index=True)
    # Shipping (step 12, migration 0014): how it goes, with which courier, its tracking number and fee
    # (charged to the customer or not); once issued, out for delivery, delivered or failed.
    delivery_method: Mapped[str | None] = mapped_column(String(12), default=None)
    courier_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_couriers.id", name="nbin_orders_courier", ondelete="SET NULL"), default=None, index=True)
    tracking_number: Mapped[str | None] = mapped_column(String(60), default=None)
    shipping_fee: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    fee_charged: Mapped[bool] = mapped_column(default=False, server_default=sa_false())
    delivery_status: Mapped[str | None] = mapped_column(String(12), default=None, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # The company's day it was delivered, for on time or late.
    delivered_on: Mapped[date | None] = mapped_column(Date, default=None)
    failed_reason: Mapped[str | None] = mapped_column(String(300), default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # The courier's proof-of-delivery photo, when the customer signed the courier's device instead.
    received_photo: Mapped[bytes | None] = mapped_column(LargeBinary, default=None, deferred=True)
    received_photo_type: Mapped[str | None] = mapped_column(String(20), default=None)
    # The wave it is picked in, with other deliveries (step 14d, migration 0018).
    wave_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    courier: Mapped[Courier | None] = relationship(lazy="joined")
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


# --- replenishment (step 15a) -------------------------------------------------------------


class ReplenishmentSettings(Base):
    """How refill is worked out (one row): safety days on every lead time, the lead time when the vendor gives
    none, the days of use the daily average looks back on, and whether drafts are made each night."""

    __tablename__ = "nbin_replenishment_settings"
    __table_args__ = (CheckConstraint("id = 1", name="one_replenishment_settings"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    safety_days: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    default_lead_days: Mapped[int] = mapped_column(Integer, default=7, server_default="7")
    history_days: Mapped[int] = mapped_column(Integer, default=90, server_default="90")
    automatic: Mapped[bool] = mapped_column(default=False, server_default=sa_false())
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Raise draft purchase orders for what an approved sales order lacks (15b).
    order_on_demand: Mapped[bool] = mapped_column(default=True, server_default=sa_true())


class ConsignmentSettlement(Base):
    """What sold from a vendor's consignment between two moments, priced at its price, sent to Finance as a bill (15d)."""

    __tablename__ = "nbin_consignment_settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("nbin_suppliers.id"), index=True)
    from_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    to_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # [{productId, sku, name, quantity, unitCost, total}]
    lines: Mapped[list[dict]] = mapped_column(JSON, default=list)
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    supplier: Mapped["Supplier"] = relationship(lazy="joined")


class ProductDocument(Base):
    """A file kept with an item (certificate of analysis, leaflet, CPR) and whether it goes with every sale (15e)."""

    __tablename__ = "nbin_product_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    file_name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(80))
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    size: Mapped[int] = mapped_column(Integer)
    send_with_sales: Mapped[bool] = mapped_column(default=True, server_default=sa_true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- units with conversions (step 14e) ----------------------------------------------------


class Packaging(Base):
    """A pack of an item (Box, Strip, Case) and how many of its base unit it holds; stock stays in the base unit."""

    __tablename__ = "nbin_product_packagings"
    __table_args__ = (CheckConstraint("quantity > 1", name="packaging_quantity"), UniqueConstraint("product_id", "name", name="packaging_name"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[int] = mapped_column(Integer)
    barcode: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- packages and waves (step 14d): pick → pack → ship -----------------------------------


class Package(Base):
    """One of a delivery's boxes: numbered, with what is in it and its weight."""

    __tablename__ = "nbin_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("nbin_orders.id", ondelete="CASCADE"), index=True)
    weight_grams: Mapped[int | None] = mapped_column(Integer, default=None)
    notes: Mapped[str | None] = mapped_column(String(300), default=None)
    packed_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    packed_by: Mapped["User | None"] = relationship(foreign_keys=[packed_by_id], lazy="joined")
    lines: Mapped[list["PackageLine"]] = relationship(back_populates="package", cascade="all, delete-orphan", lazy="selectin")


class PackageLine(Base):
    __tablename__ = "nbin_package_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="package_line_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    package_id: Mapped[str] = mapped_column(ForeignKey("nbin_packages.id", ondelete="CASCADE"), index=True)
    order_line_id: Mapped[str] = mapped_column(ForeignKey("nbin_order_lines.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)

    package: Mapped[Package] = relationship(back_populates="lines")


class Wave(Base):
    """Several held deliveries from one warehouse, picked together from one pick list."""

    __tablename__ = "nbin_waves"
    __table_args__ = (CheckConstraint("status IN ('open', 'done')", name="wave_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    notes: Mapped[str | None] = mapped_column(String(300), default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id], lazy="joined")


# --- quality checks on receipt (step 14a) -------------------------------------------------


QUALITY_REASONS = ("damaged", "expired", "short_expiry", "wrong_item", "short", "other")


class QualityCheck(Base):
    """What a receipt into a checking warehouse holds until someone checks it: passed is released for use,
    failed is put aside as damaged, with why."""

    __tablename__ = "nbin_quality_checks"
    __table_args__ = (CheckConstraint("status IN ('waiting', 'done')", name="quality_check_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    receipt_id: Mapped[str] = mapped_column(ForeignKey("nbin_receipts.id", ondelete="CASCADE"), unique=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="waiting", index=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    checked_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    receipt: Mapped["Receipt"] = relationship(lazy="joined")
    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    checked_by: Mapped[User | None] = relationship(foreign_keys=[checked_by_id], lazy="joined")
    lines: Mapped[list["QualityCheckLine"]] = relationship(
        back_populates="check", cascade="all, delete-orphan", lazy="selectin", order_by="QualityCheckLine.position"
    )


class QualityCheckLine(Base):
    __tablename__ = "nbin_quality_check_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    check_id: Mapped[str] = mapped_column(ForeignKey("nbin_quality_checks.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    product_id: Mapped[str] = mapped_column(ForeignKey("nbin_products.id"))
    location_id: Mapped[str] = mapped_column(ForeignKey("nbin_locations.id"))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_batches.id", ondelete="SET NULL"), default=None)
    quantity: Mapped[int] = mapped_column(Integer)
    passed: Mapped[int | None] = mapped_column(Integer, default=None)
    failed: Mapped[int | None] = mapped_column(Integer, default=None)
    reason: Mapped[str | None] = mapped_column(String(40), default=None)
    note: Mapped[str | None] = mapped_column(String(300), default=None)

    check: Mapped[QualityCheck] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")
    batch: Mapped["Batch | None"] = relationship(lazy="joined")


# --- transfers --------------------------------------------------------------------------


TRANSFER_STATUSES = ("draft", "requested", "approved", "in_transit", "received", "cancelled")


class Transfer(DocumentHeader, Stamped, Base):
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


class Adjustment(DocumentHeader, Stamped, Base):
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


class Count(DocumentHeader, Stamped, Base):
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
    # The schedule it was started from (step 14b, migration 0017); approving it sets the next due day.
    schedule_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    submitted_by: Mapped[User | None] = relationship(foreign_keys=[submitted_by_id], lazy="joined")
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id], lazy="joined")
    lines: Mapped[list["CountLine"]] = relationship(back_populates="count", cascade="all, delete-orphan", lazy="selectin", order_by="CountLine.position")


class CountSchedule(Stamped, Base):
    """A cycle count that comes round every so many days (step 14b): one warehouse, and one category when set."""

    __tablename__ = "nbin_count_schedules"
    __table_args__ = (CheckConstraint("every_days > 0", name="count_schedule_every"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("nbin_warehouses.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_categories.id", ondelete="SET NULL"), default=None)
    every_days: Mapped[int] = mapped_column(Integer)
    next_on: Mapped[date] = mapped_column(Date, index=True)
    last_counted_on: Mapped[date | None] = mapped_column(Date, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbin_users.id", ondelete="SET NULL"), default=None)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")


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
