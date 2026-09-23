"""Sales' tables. Changes to them go through a migration (migrations/versions).

Accounts here are Sales' own: nobody signed in here exists in any other Orbit app.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    # Switched off: kept for its history, but nobody new is put in it.
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (CheckConstraint("scope IN ('own', 'team', 'all')", name="role_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    # Whose records its permissions reach (app/permissions.py).
    scope: Mapped[str] = mapped_column(String(8), default="own")
    # Administrator: always every permission, can't be changed or deleted.
    is_system: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    grants: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def permissions(self) -> set[str]:
        return {g.permission for g in self.grants}


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)

    role: Mapped[Role] = relationship(back_populates="grants")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), index=True, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Every session started before this ends (see deps.current_user).
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    role: Mapped[Role] = relationship(lazy="joined")
    team: Mapped[Team | None] = relationship(lazy="joined")


class SignInSession(Base):
    """One sign-in. The browser holds the token; only its hash is kept here."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class AuditEntry(Base):
    """Who changed what, and when. Names the fields that changed, never their
    values, so it can be shown to admins without leaking what something was."""

    __tablename__ = "audit_log"

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


# --- customers and what's done with them --------------------------------------------
#
# Every record has an owner (a person here) and the owner's team, which is what
# a role's scope reads (app/scope.py): own records, the team's, or all of them.


class Owned:
    """Who a record belongs to. `team_id` is the owner's team when it was last
    given to them, so moving someone to another team doesn't move their records."""

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), index=True, default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


CUSTOMER_COLORS = ("gray", "brand", "green", "blue", "amber", "red", "purple", "muted")


class CustomerType(Base):
    """What kind of customer a company is: Prospect, Customer, Partner... The
    list is an administrator's to keep (Administration → Customer types)."""

    __tablename__ = "customer_types"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    color: Mapped[str] = mapped_column(String(12), default="gray")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Switched off: companies keep it, but it isn't offered any more.
    is_active: Mapped[bool] = mapped_column(default=True)


class Company(Owned, Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(16), default="prospect")
    industry: Mapped[str | None] = mapped_column(String(80), default=None)
    website: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    city: Mapped[str | None] = mapped_column(String(80), default=None)
    country: Mapped[str | None] = mapped_column(String(80), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    owner: Mapped[User] = relationship(foreign_keys="Company.owner_id", lazy="joined")
    team: Mapped[Team | None] = relationship(lazy="joined")


class Contact(Owned, Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True, default=None)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80), default=None)
    job_title: Mapped[str | None] = mapped_column(String(120), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    mobile: Mapped[str | None] = mapped_column(String(40), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    company: Mapped[Company | None] = relationship(lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys="Contact.owner_id", lazy="joined")
    team: Mapped[Team | None] = relationship(lazy="joined")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() if self.last_name else self.first_name


ACTIVITY_KINDS = ("call", "meeting", "email", "note", "task")
# Kinds that are planned first and done later; the rest are logged once they've happened.
PLANNED_KINDS = ("meeting", "task")


class Activity(Owned, Base):
    """A call, meeting, email, note or task, about a company and/or a contact.

    `at` is when it happened (call, email, note) or when it's due (meeting,
    task). A meeting or task is open until `done_at` is set; the others are done
    when logged. The owner is who did it, or who it's assigned to."""

    __tablename__ = "activities"
    __table_args__ = (CheckConstraint("kind IN ('call', 'meeting', 'email', 'note', 'task')", name="activity_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(8), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, default=None)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), index=True, default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, default=None)
    # Calls and meetings: how long, in minutes. Calls and emails: which way.
    duration_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    direction: Mapped[str | None] = mapped_column(String(8), default=None)

    company: Mapped[Company | None] = relationship(lazy="joined")
    contact: Mapped[Contact | None] = relationship(lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys="Activity.owner_id", lazy="joined")


# --- the catalogue: what's sold, and at what price ---------------------------------------
#
# Money is whole minor units (centavos) everywhere; percentages are basis points
# (1250 = 12.5%).


class PriceType(Base):
    """A way of pricing a quote: "Patient", "Drugstore/Hospital", "Special Price"."""

    __tablename__ = "price_types"
    __table_args__ = (
        CheckConstraint("entry IN ('list', 'entered')", name="price_type_entry"),
        CheckConstraint("rule IN ('always', 'with_rx')", name="price_type_rule"),
    )

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    # list: the price comes from the price list. entered: the rep types it on the quote.
    entry: Mapped[str] = mapped_column(String(8), default="list")
    # always: offered on every quote. with_rx: only when there's a prescription.
    rule: Mapped[str] = mapped_column(String(8), default="always")
    requires_notes: Mapped[bool] = mapped_column(default=False)
    needs_approval: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    generic_name: Mapped[str | None] = mapped_column(String(160), default=None)
    strength: Mapped[str | None] = mapped_column(String(60), default=None)
    form: Mapped[str | None] = mapped_column(String(60), default=None)
    unit: Mapped[str] = mapped_column(String(30), default="piece")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    prices: Mapped[list["ProductPrice"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ProductPrice(Base):
    """The company's price for a product under a price type."""

    __tablename__ = "product_prices"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(ForeignKey("price_types.code", ondelete="CASCADE"), primary_key=True)
    amount_centavos: Mapped[int] = mapped_column(Integer)


class TeamPriceType(Base):
    """The price types a team quotes with. None chosen: every one there is."""

    __tablename__ = "team_price_types"

    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(ForeignKey("price_types.code", ondelete="CASCADE"), primary_key=True)


class TeamPrice(Base):
    """A team's own price, standing over the company's for its quotes."""

    __tablename__ = "team_prices"

    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(ForeignKey("price_types.code", ondelete="CASCADE"), primary_key=True)
    amount_centavos: Mapped[int] = mapped_column(Integer)


PROMO_KINDS = ("percent", "amount", "free_goods", "tiered")


class Promo(Base):
    """A price promotion. percent: off the line. amount: off each unit.
    free_goods: buy X, get Y free. tiered: a percent that grows with quantity."""

    __tablename__ = "promos"
    __table_args__ = (CheckConstraint("kind IN ('percent', 'amount', 'free_goods', 'tiered')", name="promo_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(12))
    percent_bp: Mapped[int | None] = mapped_column(Integer, default=None)
    amount_centavos: Mapped[int | None] = mapped_column(Integer, default=None)
    buy_qty: Mapped[int | None] = mapped_column(Integer, default=None)
    free_qty: Mapped[int | None] = mapped_column(Integer, default=None)
    # [{"minQty": 20, "percentBp": 500}, ...]
    tiers: Mapped[list] = mapped_column(JSON, default=list)
    # None: every product.
    product_ids: Mapped[list | None] = mapped_column(JSON, default=None)
    starts_on: Mapped[str | None] = mapped_column(String(10), default=None)
    ends_on: Mapped[str | None] = mapped_column(String(10), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Bundle(Base):
    """Products sold together at one set price."""

    __tablename__ = "bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    price_centavos: Mapped[int] = mapped_column(Integer)
    # True: one line on the quote. False: shown as its items, sharing the set price.
    as_one_line: Mapped[bool] = mapped_column(default=True)
    # [{"productId": "...", "qty": 2}, ...]
    items: Mapped[list] = mapped_column(JSON, default=list)
    starts_on: Mapped[str | None] = mapped_column(String(10), default=None)
    ends_on: Mapped[str | None] = mapped_column(String(10), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Issuer(Base):
    """Who may pay for a quote with a guarantee letter: DSWD, PCSO..."""

    __tablename__ = "issuers"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)


class SalesSettings(Base):
    """Sales' own rules. One row."""

    __tablename__ = "sales_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # An extra discount above this, on a line, needs Finance's approval.
    discount_approval_bp: Mapped[int] = mapped_column(Integer, default=1000)
    allows_guarantee_letters: Mapped[bool] = mapped_column(default=True)
    # Retention: a customer with no quote in this many days is at risk; in this many, lost.
    at_risk_days: Mapped[int] = mapped_column(Integer, default=60)
    lost_days: Mapped[int] = mapped_column(Integer, default=90)


# --- quotes --------------------------------------------------------------------------------


class Quote(Owned, Base):
    """A priced offer to a company or a contact. Lines and totals are kept as
    priced when it was made: changing a price later never changes a quote.
    The owner is who made it."""

    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint("approval_status IN ('none', 'pending', 'approved', 'rejected')", name="quote_approval"),
        CheckConstraint("letter_status IN ('none', 'pending', 'verified', 'rejected')", name="quote_letter"),
        CheckConstraint("payment_status IN ('none', 'unpaid', 'partial', 'paid')", name="quote_payment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(24), unique=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, default=None)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), index=True, default=None)
    customer_name: Mapped[str] = mapped_column(String(200))
    price_type: Mapped[str] = mapped_column(String(40))
    price_type_name: Mapped[str] = mapped_column(String(80))
    rx: Mapped[bool] = mapped_column(default=False)
    # "self", or an issuer's code when a guarantee letter pays.
    payer: Mapped[str] = mapped_column(String(40), default="self")
    payer_name: Mapped[str | None] = mapped_column(String(120), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    gross_centavos: Mapped[int] = mapped_column(Integer, default=0)
    promo_discount_centavos: Mapped[int] = mapped_column(Integer, default=0)
    discount_centavos: Mapped[int] = mapped_column(Integer, default=0)
    total_centavos: Mapped[int] = mapped_column(Integer, default=0)

    approval_status: Mapped[str] = mapped_column(String(10), default="none", index=True)
    approval_reasons: Mapped[list] = mapped_column(JSON, default=list)
    approval_note: Mapped[str | None] = mapped_column(Text, default=None)
    approval_by_id: Mapped[str | None] = mapped_column(String(36), default=None)
    approval_by_name: Mapped[str | None] = mapped_column(String(120), default=None)
    approval_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # {"number", "issuedOn", "amountCentavos", "file": {"ref", "name", "contentType", "size", "ext"} | None}
    letter: Mapped[dict | None] = mapped_column(JSON, default=None)
    letter_status: Mapped[str] = mapped_column(String(10), default="none", index=True)
    letter_note: Mapped[str | None] = mapped_column(Text, default=None)
    letter_by_id: Mapped[str | None] = mapped_column(String(36), default=None)
    letter_by_name: Mapped[str | None] = mapped_column(String(120), default=None)
    letter_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    payment_status: Mapped[str] = mapped_column(String(10), default="none", index=True)
    paid_centavos: Mapped[int] = mapped_column(Integer, default=0)
    payments: Mapped[list] = mapped_column(JSON, default=list)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    created_by: Mapped[User] = relationship(foreign_keys="Quote.created_by_id", lazy="joined")

