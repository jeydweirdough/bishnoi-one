"""The CRM's tables. Changes to them go through a migration (migrations/versions).

Every table's name starts with nbcm_ (NaBhi CRM), so it is plain which app a
table belongs to, whatever database it ends up in.

Accounts here are the CRM's own: nobody signed in here exists in any other Nabhi app.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Team(Base):
    __tablename__ = "nbcm_teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    # The offices the team works from: ["Makati", "Cebu"].
    headquarters: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Switched off: kept for its history, but nobody new is put in it.
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Role(Base):
    __tablename__ = "nbcm_roles"
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
    __tablename__ = "nbcm_role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("nbcm_roles.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)

    role: Mapped[Role] = relationship(back_populates="grants")


class User(Base):
    __tablename__ = "nbcm_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("nbcm_roles.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_teams.id", ondelete="SET NULL"), index=True, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Every session started before this ends (see deps.current_user).
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Their Nabhi account on the platform, once they have signed in with it (app/platform_pass.py).
    platform_identity_id: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)

    role: Mapped[Role] = relationship(lazy="joined")
    team: Mapped[Team | None] = relationship(lazy="joined")


class PlatformPass(Base):
    """A pass from the platform already taken: each one works once. Kept until it would have expired."""

    __tablename__ = "nbcm_platform_passes"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SignInSession(Base):
    """One sign-in. The browser holds the token; only its hash is kept here."""

    __tablename__ = "nbcm_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbcm_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class AuditEntry(Base):
    """Who changed what, and when. Names the fields that changed, never their
    values, so it can be shown to admins without leaking what something was."""

    __tablename__ = "nbcm_audit_log"

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

    owner_id: Mapped[str] = mapped_column(ForeignKey("nbcm_users.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_teams.id", ondelete="SET NULL"), index=True, default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


CUSTOMER_COLORS = ("gray", "brand", "green", "blue", "amber", "red", "purple", "muted")


class CustomerType(Base):
    """What kind of customer a company is: Prospect, Customer, Partner... The
    list is an administrator's to keep (Administration → Customer types)."""

    __tablename__ = "nbcm_customer_types"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    color: Mapped[str] = mapped_column(String(12), default="gray")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Switched off: companies keep it, but it isn't offered any more.
    is_active: Mapped[bool] = mapped_column(default=True)


class Company(Owned, Base):
    __tablename__ = "nbcm_companies"

    # Values of the fields an admin added (Settings → Forms), by key.
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(16), default="prospect")
    # Which price group's prices it gets (Hospital, Drugstore chain...). None: none.
    price_group_code: Mapped[str | None] = mapped_column(ForeignKey("nbcm_price_groups.code", ondelete="SET NULL"), index=True, default=None)
    industry: Mapped[str | None] = mapped_column(String(80), default=None)
    # How they first came to us: one of the lead sources (Settings → Deal
    # stages), the same list deals use. A new deal starts with it.
    lead_source: Mapped[str | None] = mapped_column(String(60), default=None)
    website: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    city: Mapped[str | None] = mapped_column(String(80), default=None)
    country: Mapped[str | None] = mapped_column(String(80), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    # Where the clinic is (a doctor's), pinned by a field agent standing there,
    # so a visit can be told apart from one logged somewhere else.
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    pinned_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_users.id", ondelete="SET NULL"), default=None)

    owner: Mapped[User] = relationship(foreign_keys="Company.owner_id", lazy="joined")
    team: Mapped[Team | None] = relationship(lazy="joined")


class Contact(Owned, Base):
    __tablename__ = "nbcm_contacts"

    # Values of the fields an admin added (Settings → Forms), by key.
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_companies.id", ondelete="SET NULL"), index=True, default=None)
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

    __tablename__ = "nbcm_activities"
    __table_args__ = (CheckConstraint("kind IN ('call', 'meeting', 'email', 'note', 'task')", name="activity_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(8), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_companies.id", ondelete="CASCADE"), index=True, default=None)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_contacts.id", ondelete="SET NULL"), index=True, default=None)
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
    """A way of pricing a quote: "Patient", "Drugstore/Hospital", "Requested price"."""

    __tablename__ = "nbcm_price_types"
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
    __tablename__ = "nbcm_products"

    # Values of the fields an admin added (Settings → Forms), by key.
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    generic_name: Mapped[str | None] = mapped_column(String(160), default=None)
    strength: Mapped[str | None] = mapped_column(String(60), default=None)
    form: Mapped[str | None] = mapped_column(String(60), default=None)
    unit: Mapped[str] = mapped_column(String(30), default="piece")
    # For VAT, as Finance's tax pack names it: standard, zero_rated or exempt.
    vat_category: Mapped[str] = mapped_column(String(20), default="standard")
    is_active: Mapped[bool] = mapped_column(default=True)
    # The product in Nabhi Inventory this one is, when the list comes from there:
    # then its code, name, unit, state and SRP are Inventory's.
    inventory_id: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    prices: Mapped[list["ProductPrice"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ProductPrice(Base):
    """The company's price for a product under a price type."""

    __tablename__ = "nbcm_product_prices"

    product_id: Mapped[str] = mapped_column(ForeignKey("nbcm_products.id", ondelete="CASCADE"), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(ForeignKey("nbcm_price_types.code", ondelete="CASCADE"), primary_key=True)
    amount_centavos: Mapped[int] = mapped_column(Integer)


class TeamPriceType(Base):
    """The price types a team quotes with. None chosen: every one there is."""

    __tablename__ = "nbcm_team_price_types"

    team_id: Mapped[str] = mapped_column(ForeignKey("nbcm_teams.id", ondelete="CASCADE"), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(ForeignKey("nbcm_price_types.code", ondelete="CASCADE"), primary_key=True)


class TeamPrice(Base):
    """A team's own price, standing over the company's for its quotes."""

    __tablename__ = "nbcm_team_prices"

    team_id: Mapped[str] = mapped_column(ForeignKey("nbcm_teams.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("nbcm_products.id", ondelete="CASCADE"), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(ForeignKey("nbcm_price_types.code", ondelete="CASCADE"), primary_key=True)
    amount_centavos: Mapped[int] = mapped_column(Integer)


PROMO_KINDS = ("percent", "amount", "free_goods", "tiered")


class Promo(Base):
    """A price promotion. percent: off the line. amount: off each unit.
    free_goods: buy X, get Y free. tiered: a percent that grows with quantity."""

    __tablename__ = "nbcm_promos"
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
    # The divisions (teams) it's for. Nobody outside them sees it or quotes it.
    team_ids: Mapped[list] = mapped_column(JSON, default=list)
    starts_on: Mapped[str | None] = mapped_column(String(10), default=None)
    ends_on: Mapped[str | None] = mapped_column(String(10), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Bundle(Base):
    """Products sold together at one set price."""

    __tablename__ = "nbcm_bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    price_centavos: Mapped[int] = mapped_column(Integer)
    # True: one line on the quote. False: shown as its items, sharing the set price.
    as_one_line: Mapped[bool] = mapped_column(default=True)
    # [{"productId": "...", "qty": 2}, ...]
    items: Mapped[list] = mapped_column(JSON, default=list)
    # The divisions (teams) it's for. Nobody outside them sees it or quotes it.
    team_ids: Mapped[list] = mapped_column(JSON, default=list)
    starts_on: Mapped[str | None] = mapped_column(String(10), default=None)
    ends_on: Mapped[str | None] = mapped_column(String(10), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Issuer(Base):
    """Who may pay for a quote with a guarantee letter: DSWD, PCSO..."""

    __tablename__ = "nbcm_issuers"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)


class SalesSettings(Base):
    """The CRM's own rules. One row."""

    __tablename__ = "nbcm_sales_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # An extra discount above this, on a line, needs Finance's approval.
    discount_approval_bp: Mapped[int] = mapped_column(Integer, default=1000)
    allows_guarantee_letters: Mapped[bool] = mapped_column(default=True)
    # Retention: a customer with no quote in this many days is at risk; in this many, lost.
    at_risk_days: Mapped[int] = mapped_column(Integer, default=60)
    lost_days: Mapped[int] = mapped_column(Integer, default=90)
    # The company as the screens show it. Null: what .env says.
    org_name: Mapped[str | None] = mapped_column(String(120), default=None)
    currency: Mapped[str | None] = mapped_column(String(3), default=None)
    locale: Mapped[str | None] = mapped_column(String(20), default=None)
    timezone: Mapped[str | None] = mapped_column(String(60), default=None)
    # Quotes: numbered PREFIX-YYYYMM-####, good for this many days, on these terms.
    quote_prefix: Mapped[str] = mapped_column(String(10), default="Q")
    quote_valid_days: Mapped[int] = mapped_column(Integer, default=30)
    quote_terms: Mapped[str | None] = mapped_column(Text, default=None)
    # The letterhead of a printed quotation.
    company_address: Mapped[str | None] = mapped_column(String(300), default=None)
    company_tin: Mapped[str | None] = mapped_column(String(40), default=None)
    company_contact: Mapped[str | None] = mapped_column(String(200), default=None)
    # The last time the product list was brought over from Inventory, and why
    # the last try failed (None: it didn't).
    inventory_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    inventory_error: Mapped[str | None] = mapped_column(String(300), default=None)
    # How a line is priced, in order (app/conditions.py): where its price comes
    # from, the adjustments after it, and whether Finance adds tax.
    pricing_procedure: Mapped[dict | None] = mapped_column(JSON, default=None)
    # Whether catalogue prices already include VAT.
    prices_include_tax: Mapped[bool] = mapped_column(default=True)
    # Deals: the lists a deal's lead source and lost reason are picked from,
    # {"sources": [...], "lostReasons": [...]}. None: the starting lists.
    deal_lists: Mapped[dict | None] = mapped_column(JSON, default=None)


# --- quotes --------------------------------------------------------------------------------


class Quote(Owned, Base):
    """A priced offer to a company or a contact. Lines and totals are kept as
    priced when it was made: changing a price later never changes a quote.
    The owner is who made it."""

    __tablename__ = "nbcm_quotes"
    __table_args__ = (
        CheckConstraint("approval_status IN ('none', 'pending', 'approved', 'rejected')", name="quote_approval"),
        CheckConstraint("letter_status IN ('none', 'pending', 'verified', 'rejected')", name="quote_letter"),
        CheckConstraint("payment_status IN ('none', 'unpaid', 'partial', 'paid')", name="quote_payment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(24), unique=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_companies.id", ondelete="CASCADE"), index=True, default=None)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_contacts.id", ondelete="SET NULL"), index=True, default=None)
    # The deal it was made for, if any.
    deal_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_deals.id", ondelete="SET NULL"), index=True, default=None)
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
    # Finance's tax on it, as the invoice will show it: its summary rows and
    # the amount due. None: priced without the tax step.
    tax: Mapped[dict | None] = mapped_column(JSON, default=None)

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

    # From the quote settings when it was made: good until this day, on these terms.
    valid_until: Mapped[str | None] = mapped_column(String(10), default=None)
    terms: Mapped[str | None] = mapped_column(Text, default=None)
    # Values of the fields an admin added (Settings → Forms), by key.
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    # The order Nabhi Order made from it: {"id", "number", "url", "status", "by": {"id", "name"}, "at"}.
    # None: not ordered yet. A quote is ordered once.
    sales_order: Mapped[dict | None] = mapped_column(JSON, default=None)
    # A quote marked Rx is checked by a pharmacist in Nabhi Pharmacy before
    # it's ordered (app/pharmacy.py). What was sent: {"prescriberName",
    # "prescriberLicense", "prescriberClinic", "prescribedOn", "notes",
    # "sentBy", "sentAt"}; Pharmacy's last answer (its check_out); when it was
    # asked; and why the last try failed, if it did. None: not sent.
    pharmacy_sent: Mapped[dict | None] = mapped_column(JSON, default=None)
    pharmacy_check: Mapped[dict | None] = mapped_column(JSON, default=None)
    pharmacy_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    pharmacy_error: Mapped[str | None] = mapped_column(String(300), default=None)

    created_by: Mapped[User] = relationship(foreign_keys="Quote.created_by_id", lazy="joined")


class StoredFile(Base):
    """An uploaded file (a quote's guarantee letter), kept in the database
    itself: a server without a lasting disk (Vercel) keeps it all the same, and
    it is backed up with everything else. The quote's `letter.file.ref` names it."""

    __tablename__ = "nbcm_stored_files"

    ref: Mapped[str] = mapped_column(String(32), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- marketing requests: money asked for ahead of spending it ---------------------------------
#
# A salesperson or field agent asks here, their Team Lead approves here, and
# Nabhi Finance releases it and checks how it was spent (app/funds.py).


class FundPurpose(Base):
    """What money is asked for (a partnership dinner, transport). Whether it's
    liquidated (receipts and unused funds back) goes with the purpose; the Team Lead
    can still change it on a request when approving."""

    __tablename__ = "nbcm_fund_purposes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    liquidate: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


FUND_REQUEST_STATUSES = (
    # Here: waiting on the Team Lead, and what they decided.
    "pending", "declined", "cancelled", "approved",
    # Finance's, mirrored from it once it has the request.
    "to_release", "to_liquidate", "to_check", "to_return", "to_reimburse", "closed",
)


class FundRequest(Owned, Base):
    """One request for money. The owner is who asked, and who liquidates it."""

    __tablename__ = "nbcm_fund_requests"
    __table_args__ = (CheckConstraint(f"status IN {FUND_REQUEST_STATUSES}", name="fund_request_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(24), unique=True)
    purpose_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_fund_purposes.id", ondelete="SET NULL"), default=None)
    # As it was when asked, so renaming a purpose never rewrites a request.
    purpose_name: Mapped[str] = mapped_column(String(80))
    liquidate: Mapped[bool] = mapped_column(default=True)
    amount_centavos: Mapped[int] = mapped_column(Integer)
    needed_on: Mapped[str | None] = mapped_column(String(10), default=None)
    details: Mapped[str] = mapped_column(Text)
    # The customer it's for, if any (the partner at the dinner).
    company_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_companies.id", ondelete="SET NULL"), default=None)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # The Team Lead's decision.
    approved_centavos: Mapped[int | None] = mapped_column(Integer, default=None)
    decided_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(500), default=None)
    # Finance's copy, as it last answered, and why sending it failed (None: it didn't).
    finance: Mapped[dict | None] = mapped_column(JSON, default=None)
    finance_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finance_error: Mapped[str | None] = mapped_column(String(300), default=None)

    owner: Mapped[User] = relationship(foreign_keys="FundRequest.owner_id", lazy="joined")
    decided_by: Mapped[User | None] = relationship(foreign_keys="FundRequest.decided_by_id", lazy="joined")
    company: Mapped["Company | None"] = relationship(lazy="joined")


# --- settings: the forms (Administration → Settings → Forms) --------------------------
#
# Every form (a company, a contact, a product, a quote) is laid out in sections,
# and every field on it is a row here: the built-in ones (name, email...) and
# the ones an admin added. Built-in fields keep their values in the record's
# own columns; added ones in its `extra`, under their key.

FORM_ENTITIES = ("company", "contact", "product", "quote")
# Kinds an admin can add. Built-in fields have their own kinds too (status, owner...).
FIELD_TYPES = ("text", "long_text", "number", "money", "date", "choice", "multi_choice", "yes_no", "email", "phone", "url")


class FormSection(Base):
    __tablename__ = "nbcm_form_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity: Mapped[str] = mapped_column(String(12), index=True)
    title: Mapped[str] = mapped_column(String(80))
    # 1 or 2: how many fields sit side by side.
    columns: Mapped[int] = mapped_column(Integer, default=2)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class FormField(Base):
    __tablename__ = "nbcm_form_fields"
    __table_args__ = (UniqueConstraint("entity", "key", name="uq_form_field_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity: Mapped[str] = mapped_column(String(12), index=True)
    # Built-in: the field's name in the API ("industry", "jobTitle"). Added: "x_..."
    # made from its first label, and never changed: it's where values are kept.
    key: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(12))
    # Built in: can't be deleted, and its kind can't change.
    standard: Mapped[bool] = mapped_column(default=False)
    # The record can't do without it: always shown, always required.
    locked: Mapped[bool] = mapped_column(default=False)
    required: Mapped[bool] = mapped_column(default=False)
    # Taken off the form (built-in fields are hidden, never deleted).
    hidden: Mapped[bool] = mapped_column(default=False)
    in_list: Mapped[bool] = mapped_column(default=False)
    # For a pick list: what can be picked.
    options: Mapped[list] = mapped_column(JSON, default=list)
    help_text: Mapped[str | None] = mapped_column(String(200), default=None)
    placeholder: Mapped[str | None] = mapped_column(String(80), default=None)
    section_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_form_sections.id", ondelete="SET NULL"), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


# --- field work: visiting doctors, collecting what they owe -----------------------------
#
# Field agents visit doctors (customers of the type "doctor") and collect
# payments. What each doctor owes comes from accounting, uploaded now and then
# as a balance "as of" a date; collections recorded on visits after that date
# bring it down. Each agent has monthly goals, set by an administrator.

VISIT_OUTCOMES = ("collected", "promised", "not_in", "updated", "other")
# How a doctor took a product that was detailed to them, best first.
DETAIL_REACTIONS = ("will_prescribe", "already_prescribes", "interested", "neutral", "concerns", "not_interested")


class Balance(Base):
    """What a doctor owed on a date, as accounting said (Field work → Upload
    balances). The newest one counts; older ones stay as the history."""

    __tablename__ = "nbcm_balances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("nbcm_companies.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    amount_centavos: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Visit(Owned, Base):
    """A field agent's visit to a doctor, and what came of it: a payment
    collected (with its receipt), a promise to pay, nobody in, details updated."""

    __tablename__ = "nbcm_visits"
    __table_args__ = (
        CheckConstraint("outcome IN ('collected', 'promised', 'not_in', 'updated', 'other')", name="visit_outcome"),
        CheckConstraint("amount_centavos >= 0", name="visit_amount"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("nbcm_companies.id", ondelete="CASCADE"), index=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    outcome: Mapped[str] = mapped_column(String(10), index=True)
    amount_centavos: Mapped[int] = mapped_column(Integer, default=0)
    receipt_no: Mapped[str | None] = mapped_column(String(40), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    # Where the phone was when the visit was logged, if it said; and how far
    # that was from the clinic's pin, if it has one.
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    accuracy_m: Mapped[int | None] = mapped_column(Integer, default=None)
    distance_m: Mapped[int | None] = mapped_column(Integer, default=None)
    # What was detailed, in the order it was (P6): [{"productId", "productName",
    # "message", "reaction"}], the reaction one of DETAIL_REACTIONS. And what the
    # next visit is for, shown when that visit is logged.
    detailing: Mapped[list] = mapped_column(JSON, default=list)
    next_objective: Mapped[str | None] = mapped_column(String(300), default=None)

    company: Mapped[Company] = relationship(lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys="Visit.owner_id", lazy="joined")


class FieldGoal(Base):
    """One person's goals for one month (YYYY-MM), set by an administrator."""

    __tablename__ = "nbcm_field_goals"
    __table_args__ = (UniqueConstraint("user_id", "month", name="field_goal_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbcm_users.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    doctors_visited: Mapped[int] = mapped_column(Integer, default=0)
    doctors_updated: Mapped[int] = mapped_column(Integer, default=0)
    amount_centavos: Mapped[int] = mapped_column(Integer, default=0)
    collection_visits: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TrailBatch(Base):
    """Where a field agent went while the CRM was open: one row per upload
    (about every 15 minutes), its points packed (app/trail.py). Kept 90 days;
    the day's RouteDay stays after that."""

    __tablename__ = "nbcm_trail_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbcm_users.id", ondelete="CASCADE"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD, the company's own
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer)
    points: Mapped[str] = mapped_column(Text)
    # The box the points fall in, to find batches near a place without unpacking.
    min_lat: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    min_lng: Mapped[float] = mapped_column(Float)
    max_lng: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RouteDay(Base):
    """One person's day on the road, summed up as their trail comes in."""

    __tablename__ = "nbcm_route_days"
    __table_args__ = (UniqueConstraint("user_id", "day", name="route_day_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbcm_users.id", ondelete="CASCADE"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    distance_m: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The day's last point so far, so the next batch's distance joins on.
    last_lat: Mapped[float] = mapped_column(Float)
    last_lng: Mapped[float] = mapped_column(Float)


# --- price rules (app/conditions.py) ------------------------------------------------------------


class PriceGroup(Base):
    """A group of customers priced alike: Hospital, Drugstore chain, Clinic."""

    __tablename__ = "nbcm_price_groups"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


CONDITION_KINDS = ("group_price", "volume", "surcharge")


class PriceCondition(Base):
    """One pricing rule, over the days it applies.

    group_price: a unit price for a price group (and optionally one price type).
    volume: a percent off that grows with quantity (tiers).
    surcharge: an amount added per unit, or a percent of the line.
    A product of None: every product. A group of None: every customer."""

    __tablename__ = "nbcm_price_conditions"
    __table_args__ = (CheckConstraint("kind IN ('group_price', 'volume', 'surcharge')", name="condition_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    name: Mapped[str] = mapped_column(String(120))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_products.id", ondelete="CASCADE"), index=True, default=None)
    price_group_code: Mapped[str | None] = mapped_column(ForeignKey("nbcm_price_groups.code", ondelete="CASCADE"), index=True, default=None)
    price_type_code: Mapped[str | None] = mapped_column(ForeignKey("nbcm_price_types.code", ondelete="CASCADE"), default=None)
    amount_centavos: Mapped[int | None] = mapped_column(Integer, default=None)
    percent_bp: Mapped[int | None] = mapped_column(Integer, default=None)
    # volume: [{"minQty": 20, "percentBp": 300}, ...]
    tiers: Mapped[list] = mapped_column(JSON, default=list)
    starts_on: Mapped[str | None] = mapped_column(String(10), default=None)
    ends_on: Mapped[str | None] = mapped_column(String(10), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# --- quotation templates: how a printed quote looks, per guarantee-letter issuer ---------------


class QuoteTemplate(Base):
    """A quotation form an admin set up: designed here ("form"), or their own
    Excel form uploaded and filled in ("excel"). Picked for a quote by who pays
    (an issuer's code, "self" for the customer, None for any) and its team."""

    __tablename__ = "nbcm_quote_templates"
    __table_args__ = (CheckConstraint("kind IN ('form', 'excel')", name="quote_template_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(8), default="form")
    payer: Mapped[str | None] = mapped_column(String(40), default=None)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_teams.id", ondelete="SET NULL"), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Control numbers: PREFIX-YYYY-MM-00001, counting on from control_next.
    control_prefix: Mapped[str | None] = mapped_column(String(20), default=None)
    control_next: Mapped[int] = mapped_column(Integer, default=1)
    control_digits: Mapped[int] = mapped_column(Integer, default=4)
    # The form's words and letterhead (app/quote_templates.py DESIGN).
    design: Mapped[dict] = mapped_column(JSON, default=dict)
    # Stored files (nbcm_stored_files refs).
    logo_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    signature_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    excel_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    excel_name: Mapped[str | None] = mapped_column(String(200), default=None)
    excel_sheet: Mapped[str | None] = mapped_column(String(120), default=None)
    # Where the form's parts were found on the sheet (app/quote_templates.py find()).
    excel_map: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class QuoteControl(Base):
    """The control number a quote got on a template, the first time it was
    printed or downloaded with it; the same number every time after."""

    __tablename__ = "nbcm_quote_controls"
    __table_args__ = (
        UniqueConstraint("template_id", "quote_id", name="quote_control_once"),
        UniqueConstraint("template_id", "number", name="quote_control_number_once"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    template_id: Mapped[str] = mapped_column(ForeignKey("nbcm_quote_templates.id", ondelete="CASCADE"), index=True)
    quote_id: Mapped[str] = mapped_column(ForeignKey("nbcm_quotes.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- deals (benchmarks decision D2) ------------------------------------------------------
#
# A lead stays a customer status. Customers get deals: each with a stage, an
# expected value and close date, and a forecast category kept apart from the
# stage (Salesforce's pipeline idea). A won deal leads to a quote.

FORECAST_CATEGORIES = ("pipeline", "best_case", "commit", "closed", "omitted")


class DealStage(Base):
    """A step a deal goes through: Qualify, Proposal, Negotiation... The list is
    an administrator's to keep. Each open stage gives a new deal in it a
    probability and a forecast category; the two closed stages, won and lost,
    are always there and can only be renamed."""

    __tablename__ = "nbcm_deal_stages"
    __table_args__ = (
        CheckConstraint("outcome IN ('open', 'won', 'lost')", name="deal_stage_outcome"),
        CheckConstraint("forecast_category IN ('pipeline', 'best_case', 'commit', 'closed', 'omitted')", name="deal_stage_forecast"),
        CheckConstraint("probability >= 0 AND probability <= 100", name="deal_stage_probability"),
    )

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    outcome: Mapped[str] = mapped_column(String(8), default="open")
    probability: Mapped[int] = mapped_column(Integer, default=10)
    forecast_category: Mapped[str] = mapped_column(String(12), default="pipeline")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Switched off: deals keep it, but it isn't offered any more.
    is_active: Mapped[bool] = mapped_column(default=True)


class Deal(Owned, Base):
    """Business expected from a customer: how much, by when, and how likely.

    Its value is the products on it, priced by the price rules (as a quote
    would be, without tax), or a figure typed in when it has none. The owner
    is who's working it."""

    __tablename__ = "nbcm_deals"
    __table_args__ = (
        CheckConstraint("forecast_category IN ('pipeline', 'best_case', 'commit', 'closed', 'omitted')", name="deal_forecast"),
        CheckConstraint("probability >= 0 AND probability <= 100", name="deal_probability"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    company_id: Mapped[str] = mapped_column(ForeignKey("nbcm_companies.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_contacts.id", ondelete="SET NULL"), index=True, default=None)
    stage_code: Mapped[str] = mapped_column(ForeignKey("nbcm_deal_stages.code"), index=True)
    probability: Mapped[int] = mapped_column(Integer, default=10)
    forecast_category: Mapped[str] = mapped_column(String(12), default="pipeline", index=True)
    value_centavos: Mapped[int] = mapped_column(Integer, default=0)
    # YYYY-MM-DD, in the company's own calendar.
    expected_close_on: Mapped[str] = mapped_column(String(10), index=True)
    # Where the business came from, from the list in deal settings.
    lead_source: Mapped[str | None] = mapped_column(String(60), default=None)
    # The products on it, priced at this price type: [{productId, productName,
    # unit, quantity, unitPriceCentavos, totalCentavos}].
    price_type: Mapped[str | None] = mapped_column(String(40), default=None)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    # Closing: when, why it was lost and to whom, and the quote that won it.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, default=None)
    lost_reason: Mapped[str | None] = mapped_column(String(80), default=None)
    competitor: Mapped[str | None] = mapped_column(String(120), default=None)
    # Not a foreign key: quotes already point at deals, and a deleted quote
    # leaves the deal won all the same.
    won_quote_id: Mapped[str | None] = mapped_column(String(36), default=None)

    company: Mapped[Company] = relationship(lazy="joined")
    contact: Mapped[Contact | None] = relationship(lazy="joined")
    stage: Mapped[DealStage] = relationship(lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys="Deal.owner_id", lazy="joined")


class RevenueTarget(Base):
    """What one person is expected to sell in one month (YYYY-MM): the value of
    the deals they win. A team's target is its people's added up. Set by whoever
    sets goals (goals.manage)."""

    __tablename__ = "nbcm_revenue_targets"
    __table_args__ = (UniqueConstraint("user_id", "month", name="revenue_target_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbcm_users.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    amount_centavos: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MergedRecord(Base):
    """A customer or contact merged into another (Customers → Possible
    duplicates). The merged one is gone; its id still leads to the one kept, for
    old links and for the other Nabhi apps that saved it."""

    __tablename__ = "nbcm_merged_records"

    old_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # company | contact
    new_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(200))
    merged_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_users.id", ondelete="SET NULL"), default=None)
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotDuplicate(Base):
    """Two records someone said are different, so they aren't offered again.
    The pair is kept in id order, smaller first."""

    __tablename__ = "nbcm_not_duplicates"
    __table_args__ = (UniqueConstraint("kind", "first_id", "second_id", name="not_duplicate_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16))
    first_id: Mapped[str] = mapped_column(String(36), index=True)
    second_id: Mapped[str] = mapped_column(String(36), index=True)
    decided_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbcm_users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
