"""The Pharmacy's tables. Changes to them go through a migration (migrations/versions).

Every table's name starts with nbph_ (NaBhi PHarmacy), so it is plain which
app a table belongs to, whatever database it ends up in.

Accounts here are the Pharmacy's own: nobody signed in here exists in any other Nabhi app.

Money is kept in centavos (whole numbers), never as a float.

The order of work, which the tables follow:

    prescription received -> checked -> verified -> dispensed (from a batch) -> sold

A prescription is checked and verified *before* anything is dispensed from it,
and only a verified one can be dispensed. Dispensing picks the batch each unit
comes from, takes it off that batch's stock, and records the sale.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


# --- accounts and administration ----------------------------------------------------


class Role(Base):
    __tablename__ = "nbph_roles"

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
    __tablename__ = "nbph_role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("nbph_roles.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)

    role: Mapped[Role] = relationship(back_populates="grants")


class User(Base):
    __tablename__ = "nbph_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("nbph_roles.id"), index=True)
    # A pharmacist's licence number, printed beside their name on what they verify.
    license_no: Mapped[str | None] = mapped_column(String(40), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Every session started before this ends (see deps.current_user).
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Their Nabhi account on the platform, once they have signed in with it (app/platform_pass.py).
    platform_identity_id: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)

    role: Mapped[Role] = relationship(lazy="joined")


class PlatformPass(Base):
    """A pass from the platform already taken: each one works once. Kept until it would have expired."""

    __tablename__ = "nbph_platform_passes"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SignInSession(Base):
    """One sign-in. The browser holds the token; only its hash is kept here."""

    __tablename__ = "nbph_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbph_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class AuditEntry(Base):
    """Who changed what, and when. Names the fields that changed, never their
    values, so it can be shown to admins without leaking what something was."""

    __tablename__ = "nbph_audit_log"

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


class Counter(Base):
    """The last number handed out per kind and year: RX-2026-00125 is the 125th
    prescription of 2026. Taken inside the same transaction as the record."""

    __tablename__ = "nbph_counters"

    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


# --- medicines ------------------------------------------------------------------------


class Category(Base):
    __tablename__ = "nbph_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Brand(Base):
    __tablename__ = "nbph_brands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    manufacturer: Mapped[str | None] = mapped_column(String(160), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# otc: sold over the counter. rx: dispensed only against a verified
# prescription. dangerous: an rx medicine under stricter control (a licensed
# prescriber's number is required before it can be verified).
RX_CLASSES = ("otc", "rx", "dangerous")
# active: stocked and sold. inactive: paused, kept on record.
# discontinued: never coming back; what's left can still be dispensed.
MEDICINE_STATUSES = ("active", "inactive", "discontinued")


class Medicine(Base):
    __tablename__ = "nbph_medicines"
    __table_args__ = (
        CheckConstraint("rx_class IN ('otc', 'rx', 'dangerous')", name="medicine_rx_class"),
        CheckConstraint("status IN ('active', 'inactive', 'discontinued')", name="medicine_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    generic_name: Mapped[str] = mapped_column(String(160), index=True)
    brand_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_brands.id", ondelete="SET NULL"), index=True, default=None)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_categories.id", ondelete="SET NULL"), index=True, default=None)
    strength: Mapped[str | None] = mapped_column(String(40), default=None)
    dosage_form: Mapped[str] = mapped_column(String(40))
    # What one unit is, as it is counted and sold: tablet, capsule, bottle.
    unit: Mapped[str] = mapped_column(String(20), default="piece")
    rx_class: Mapped[str] = mapped_column(String(12), default="rx")
    price_centavos: Mapped[int] = mapped_column(Integer, default=0)
    # At or below this many units on hand it is low stock.
    reorder_level: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    brand: Mapped[Brand | None] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")

    @property
    def label(self) -> str:
        """Amoxicillin 500 mg capsule (Amoxil)."""
        words = " ".join(w for w in (self.generic_name, self.strength, self.dosage_form) if w)
        return f"{words} ({self.brand.name})" if self.brand else words


# --- suppliers, batches and stock ------------------------------------------------------


class Supplier(Base):
    __tablename__ = "nbph_suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    contact_person: Mapped[str | None] = mapped_column(String(120), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Receiving(Base):
    """One delivery taken in: which supplier, their invoice, and the batches it brought."""

    __tablename__ = "nbph_receivings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_suppliers.id", ondelete="SET NULL"), index=True, default=None)
    reference: Mapped[str | None] = mapped_column(String(80), default=None)
    received_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    received_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    supplier: Mapped[Supplier | None] = relationship(lazy="joined")
    received_by: Mapped[User | None] = relationship(lazy="joined")


# available: can be dispensed and sold. quarantined: held back while it's
# looked into. recalled: withdrawn for good; never dispensed again.
BATCH_STATUSES = ("available", "quarantined", "recalled")


class Batch(Base):
    """One lot of one medicine: its expiry, what came in and what is left."""

    __tablename__ = "nbph_batches"
    __table_args__ = (
        UniqueConstraint("medicine_id", "lot_no", name="batch_lot"),
        CheckConstraint("status IN ('available', 'quarantined', 'recalled')", name="batch_status"),
        CheckConstraint("qty_on_hand >= 0", name="batch_not_negative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    medicine_id: Mapped[str] = mapped_column(ForeignKey("nbph_medicines.id"), index=True)
    lot_no: Mapped[str] = mapped_column(String(60))
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_suppliers.id", ondelete="SET NULL"), index=True, default=None)
    receiving_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_receivings.id", ondelete="SET NULL"), index=True, default=None)
    manufactured_on: Mapped[date | None] = mapped_column(Date, default=None)
    expires_on: Mapped[date] = mapped_column(Date, index=True)
    cost_centavos: Mapped[int] = mapped_column(Integer, default=0)
    qty_received: Mapped[int] = mapped_column(Integer, default=0)
    qty_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="available")
    # Why it was quarantined or recalled.
    status_reason: Mapped[str | None] = mapped_column(String(300), default=None)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    medicine: Mapped[Medicine] = relationship(lazy="joined")
    supplier: Mapped[Supplier | None] = relationship(lazy="joined")


# What moved stock, and which way. Quantities are signed: + in, - out.
MOVEMENT_KINDS = ("receive", "dispense", "sale", "adjust", "return")


class StockMovement(Base):
    """Every change to a batch's quantity, so what's on hand can always be explained."""

    __tablename__ = "nbph_stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    medicine_id: Mapped[str] = mapped_column(ForeignKey("nbph_medicines.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("nbph_batches.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    # What was on hand in the batch after it.
    balance: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(300), default=None)
    # The record that caused it: RX-, DS-, SI-, RT-, RC- numbers, for the screens.
    reference: Mapped[str | None] = mapped_column(String(20), default=None)
    by_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_users.id", ondelete="SET NULL"), default=None)

    medicine: Mapped[Medicine] = relationship(lazy="joined")
    batch: Mapped[Batch] = relationship(lazy="joined")
    by: Mapped[User | None] = relationship(lazy="joined")


# --- patients and customers -------------------------------------------------------------

# patient: someone medicines are dispensed to on a prescription.
# customer: someone who buys over the counter, kept for their history.
PERSON_KINDS = ("patient", "customer")


class Patient(Base):
    __tablename__ = "nbph_patients"
    __table_args__ = (CheckConstraint("kind IN ('patient', 'customer')", name="patient_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(10), default="patient")
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date, default=None)
    sex: Mapped[str | None] = mapped_column(String(10), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    # Shown on every prescription check, so nobody dispenses into one.
    allergies: Mapped[str | None] = mapped_column(String(500), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# --- prescriptions ------------------------------------------------------------------------

# received: in the inbox, nobody has started checking it.
# pending: checking has started; saved part-way.
# verified: every check passed; it goes to the dispensing queue.
# needs_clarification: something must be asked of the prescriber or patient.
# rejected: it won't be dispensed.
PRESCRIPTION_STATUSES = ("received", "pending", "verified", "needs_clarification", "rejected")

# What the pharmacist checks, in the order they're checked.
CHECKS = (
    ("patient", "Patient information"),
    ("prescriber", "Prescriber information"),
    ("date", "Prescription date"),
    ("medicine", "Medicine name"),
    ("strength", "Strength"),
    ("form", "Dosage form"),
    ("quantity", "Quantity"),
    ("directions", "Directions"),
    ("required", "Required prescription details"),
    ("availability", "Medicine availability"),
)
CHECK_KEYS = tuple(k for k, _ in CHECKS)


class Prescription(Base):
    __tablename__ = "nbph_prescriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'pending', 'verified', 'needs_clarification', 'rejected')", name="prescription_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("nbph_patients.id"), index=True)
    prescriber_name: Mapped[str] = mapped_column(String(120))
    prescriber_license: Mapped[str | None] = mapped_column(String(40), default=None)
    prescriber_clinic: Mapped[str | None] = mapped_column(String(160), default=None)
    prescribed_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(24), default="received", index=True)
    # {"patient": true, "prescriber": false, ...}: the pharmacist's ticks.
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    verification_notes: Mapped[str | None] = mapped_column(Text, default=None)
    checked_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_users.id", ondelete="SET NULL"), default=None)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    received_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_users.id", ondelete="SET NULL"), default=None)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    patient: Mapped[Patient] = relationship(lazy="joined")
    checked_by: Mapped[User | None] = relationship(foreign_keys="Prescription.checked_by_id", lazy="joined")
    received_by: Mapped[User | None] = relationship(foreign_keys="Prescription.received_by_id", lazy="joined")
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", lazy="selectin", order_by="PrescriptionItem.position"
    )


class PrescriptionItem(Base):
    """One medicine on a prescription, as written, and matched to the catalogue when checked."""

    __tablename__ = "nbph_prescription_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="item_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prescription_id: Mapped[str] = mapped_column(ForeignKey("nbph_prescriptions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    # As the prescriber wrote it.
    written_as: Mapped[str] = mapped_column(String(200))
    # The catalogue medicine it is, once matched.
    medicine_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_medicines.id"), index=True, default=None)
    quantity: Mapped[int] = mapped_column(Integer)
    directions: Mapped[str | None] = mapped_column(String(300), default=None)
    qty_dispensed: Mapped[int] = mapped_column(Integer, default=0)

    prescription: Mapped[Prescription] = relationship(back_populates="items")
    medicine: Mapped[Medicine | None] = relationship(lazy="joined")

    @property
    def remaining(self) -> int:
        return max(0, self.quantity - self.qty_dispensed)


# --- dispensing ---------------------------------------------------------------------------


class Dispensing(Base):
    """One hand-over against a verified prescription. A prescription may take
    several (a partial fill now, the rest when stock comes in)."""

    __tablename__ = "nbph_dispensings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    prescription_id: Mapped[str] = mapped_column(ForeignKey("nbph_prescriptions.id"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("nbph_patients.id"), index=True)
    dispensed_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_users.id", ondelete="SET NULL"), default=None)
    dispensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    sale_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_sales.id", ondelete="SET NULL"), default=None)

    prescription: Mapped[Prescription] = relationship(lazy="joined")
    patient: Mapped[Patient] = relationship(lazy="joined")
    dispensed_by: Mapped[User | None] = relationship(lazy="joined")
    lines: Mapped[list["DispensingLine"]] = relationship(back_populates="dispensing", cascade="all, delete-orphan", lazy="selectin")


class DispensingLine(Base):
    __tablename__ = "nbph_dispensing_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="dispensing_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dispensing_id: Mapped[str] = mapped_column(ForeignKey("nbph_dispensings.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("nbph_prescription_items.id"), index=True)
    medicine_id: Mapped[str] = mapped_column(ForeignKey("nbph_medicines.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("nbph_batches.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)

    dispensing: Mapped[Dispensing] = relationship(back_populates="lines")
    medicine: Mapped[Medicine] = relationship(lazy="joined")
    batch: Mapped[Batch] = relationship(lazy="joined")


# --- sales, returns and refunds -------------------------------------------------------------

# counter: sold over the counter (non-prescription only). dispensing: the sale a dispensing made.
SALE_SOURCES = ("counter", "dispensing")
PAYMENT_METHODS = ("cash", "card", "ewallet", "other")


class Sale(Base):
    __tablename__ = "nbph_sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    source: Mapped[str] = mapped_column(String(12), default="counter", index=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_patients.id", ondelete="SET NULL"), index=True, default=None)
    sold_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_users.id", ondelete="SET NULL"), default=None)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    subtotal_centavos: Mapped[int] = mapped_column(Integer, default=0)
    discount_centavos: Mapped[int] = mapped_column(Integer, default=0)
    total_centavos: Mapped[int] = mapped_column(Integer, default=0)
    payment_method: Mapped[str] = mapped_column(String(12), default="cash")
    # What has been paid back on it, across its returns.
    refunded_centavos: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    patient: Mapped[Patient | None] = relationship(lazy="joined")
    sold_by: Mapped[User | None] = relationship(lazy="joined")
    lines: Mapped[list["SaleLine"]] = relationship(back_populates="sale", cascade="all, delete-orphan", lazy="selectin")


class SaleLine(Base):
    __tablename__ = "nbph_sale_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="sale_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sale_id: Mapped[str] = mapped_column(ForeignKey("nbph_sales.id", ondelete="CASCADE"), index=True)
    medicine_id: Mapped[str] = mapped_column(ForeignKey("nbph_medicines.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("nbph_batches.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_centavos: Mapped[int] = mapped_column(Integer)
    line_total_centavos: Mapped[int] = mapped_column(Integer)
    qty_returned: Mapped[int] = mapped_column(Integer, default=0)

    sale: Mapped[Sale] = relationship(back_populates="lines")
    medicine: Mapped[Medicine] = relationship(lazy="joined")
    batch: Mapped[Batch] = relationship(lazy="joined")


class SaleReturn(Base):
    """Medicines brought back on a sale, and what was paid back for them (a refund
    may be nothing, as for an exchange)."""

    __tablename__ = "nbph_returns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    sale_id: Mapped[str] = mapped_column(ForeignKey("nbph_sales.id"), index=True)
    reason: Mapped[str] = mapped_column(String(300))
    # Back on the shelf (sealed, undamaged) or not.
    restocked: Mapped[bool] = mapped_column(default=False)
    refund_centavos: Mapped[int] = mapped_column(Integer, default=0)
    refund_method: Mapped[str | None] = mapped_column(String(12), default=None)
    by_id: Mapped[str | None] = mapped_column(ForeignKey("nbph_users.id", ondelete="SET NULL"), default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    # [{"saleLineId": ..., "quantity": 2}]
    lines: Mapped[list[dict]] = mapped_column(JSON, default=list)

    sale: Mapped[Sale] = relationship(lazy="joined")
    by: Mapped[User | None] = relationship(lazy="joined")
