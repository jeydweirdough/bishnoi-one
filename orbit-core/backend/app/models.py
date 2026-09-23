"""Accounts database: companies, people, teams, roles and who can do what; and
the price book (price types, each division's pricing rules, products, prices,
promos).

SQLite for now; the same models run on Supabase Postgres. `profiles.id` is the
user id Supabase Auth will issue, and `local_credentials` (bcrypt, which
Supabase can import) is dropped once Supabase handles sign-in.

Companies: every table below `Membership` belongs to one company and carries
`org_id` (see app/tenancy.py for the wall that keeps them apart). Natural keys
(a division's code, a role's key...) are unique inside a company, so two
companies can both have a "b2c" division; every link between these tables
includes the company, so nothing can point at another company's row.

Teams are keyed by (division_code, code) all the way down. There is no
standalone subdivision id to join on, so nothing can reference a team without
its division.

Money is whole centavos (integers), never floats. Percentages are basis
points: 1250 is 12.5%.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    LargeBinary,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.tenancy import TenantKey, TenantRow


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# --- shared by every company ---------------------------------------------------------


class Organization(Base):
    """A company using the platform. Its settings shape how its people's screens behave."""

    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint("status IN ('active', 'suspended')", name="organization_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="active")
    # The starting setup it was created from (app/templates).
    template: Mapped[str] = mapped_column(String(40), default="generic_b2b")
    currency: Mapped[str] = mapped_column(String(3), default="PHP")
    minor_units: Mapped[int] = mapped_column(Integer, default=2)
    locale: Mapped[str] = mapped_column(String(16), default="en-PH")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Manila")
    brand_name: Mapped[str] = mapped_column(String(80))
    # Order numbers start with this: GM-20260919-0001.
    order_prefix: Mapped[str] = mapped_column(String(8), default="OR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base):
    """A person. One per email across the platform; what they can do is per company."""

    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    # Off everywhere at once (a platform-wide switch); per-company access is Membership.status.
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="Assignment.created_at"
    )


class LocalCredential(Base):
    """Password hashes for the local sign-in. Supabase Auth replaces this table."""

    __tablename__ = "local_credentials"

    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProfilePhoto(Base):
    """A person's picture: 256px square WebP (app/photos.py). Shared, like the
    person; someone in two companies looks the same in both. Without one, the
    screens draw their initials."""

    __tablename__ = "profile_photos"

    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(40), default="image/webp")
    data: Mapped[bytes] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PlatformAdmin(Base):
    """Who may create and suspend companies. Never granted through a company's roles."""

    __tablename__ = "platform_admins"

    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SsoClient(Base):
    """An app people sign in to through Orbit (the Orders app). Registered with app/tools/sso_client.py."""

    __tablename__ = "sso_clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    # sha256 of the client secret, which is shown once and never kept.
    secret_hash: Mapped[str] = mapped_column(String(64))
    # Exact addresses Orbit may send people back to, with their one-time code.
    redirect_uris: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- one company's -------------------------------------------------------------------


class Membership(TenantKey, Base):
    """A person belongs to a company. Switching them off here ends their access to it only."""

    __tablename__ = "memberships"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "manager_id"], ["memberships.org_id", "memberships.user_id"]),
        CheckConstraint("status IN ('active', 'suspended')", name="membership_status"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    # Whoever set this company up, and whoever they have since trusted with it.
    # Owners hold the decisions that shape the whole company — what it is, how
    # its money reads, its data going in and out — which is more than running
    # it day to day. A company always keeps at least one.
    is_owner: Mapped[bool] = mapped_column(default=False)
    # Their manager in the same company, as its HR system records it (read-only in Orbit).
    manager_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # The one job title they hold here. It is recorded and reported on; it is
    # never read when deciding what they may do (see Position).
    position_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppLink(TenantKey, Base):
    """Another application this company reaches from Orbit.

    Orbit is the hub: people, customers, products, prices and roles live here,
    and other applications do their own work beside it. Where each one lives is
    this company's to say, not a deployment setting — adding a second warehouse
    app, or an HR portal, should be an admin typing a name and a link, not an
    environment variable and a redeploy.

    The split is the same as departments: code says what an application can *do*
    (the Orders app's eighteen steps are in app/modules.py, because they are
    real capabilities with permissions attached), data says which applications
    this company has and where they are. A built-in app gets a row here the
    first time the company is seeded, with no address until someone sets one;
    a company-added one is a row and nothing else.

    Switched off, never deleted: a link someone retires should stop appearing
    without taking its name out of the audit log.
    """

    __tablename__ = "app_links"

    # Matches a Kind.APP module's key for the built-in ones ("orders"); a slug
    # of the name for anything a company adds.
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    # Empty until someone says where it is. Until then it isn't offered.
    url: Mapped[str] = mapped_column(String(300), default="")
    # One line under the name on Settings -> Apps, for whoever wonders what it is.
    description: Mapped[str] = mapped_column(String(200), default="")
    # An icon name from the frontend's registry; None uses a default.
    icon: Mapped[str | None] = mapped_column(String(40), default=None)
    # True for the ones Orbit ships with: their permissions live in code, so
    # they can be renamed and pointed elsewhere but not removed.
    is_built_in: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Division(TenantKey, Base):
    """A division or department. The built-in ones are seeded from app/modules.py
    and bring their own screens; admins add departments of their own in Settings
    -> Teams, and those hold teams and people without screens (see
    app/catalogue.py). Switched off, never deleted, so their records keep a home."""

    __tablename__ = "divisions"
    __table_args__ = (CheckConstraint("kind IN ('sales', 'department')", name="division_kind"),)

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16), default="department")
    # An icon name from the frontend's registry. None means the built-in one.
    icon: Mapped[str | None] = mapped_column(String(40), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    subdivisions: Mapped[list["Subdivision"]] = relationship(
        back_populates="division", order_by="Subdivision.sort_order"
    )


class Subdivision(TenantKey, Base):
    """A team inside a division, e.g. (bnb, md-telesales)."""

    __tablename__ = "subdivisions"
    __table_args__ = (ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),)

    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    division: Mapped[Division] = relationship(back_populates="subdivisions")
    headquarters: Mapped[list["Headquarters"]] = relationship(
        back_populates="subdivision", order_by="Headquarters.name"
    )


class Headquarters(TenantKey, Base):
    """An optional location under a team (CEBU, DAVAO...). Not every team has one."""

    __tablename__ = "headquarters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "division_code", "subdivision_code"],
            ["subdivisions.org_id", "subdivisions.division_code", "subdivisions.code"],
        ),
    )

    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    subdivision_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True)

    subdivision: Mapped[Subdivision] = relationship(back_populates="headquarters")


class Role(TenantKey, Base):
    """What somebody may do. Always the company's, never a department's.

    A role carries permissions; where they apply is the assignment's business,
    not the role's. "Team Leader in B2B" is this role plus that scope, so a
    company never accumulates a role per department -- which is what makes the
    same nine roles work for every company on the platform.

    What a *department* names is a Position (its own table): a job title, held
    by its people, granting nothing. The two were briefly conflated by a
    `division_code` column here; 0029 removed it.
    """

    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Position(TenantRow, Base):
    """What a person's job is called. Never what they may do.

    A position is the org chart's word -- Pharmacist, Sales Representative,
    Procurement Officer -- and a role is Orbit's. They are deliberately separate
    tables with no link between them: a Sales Manager may hold Team Leader or
    Employee, and the same title means different authority in two companies.
    Reading permissions off a job title is how a rename quietly becomes a
    privilege change, so nothing here is consulted by app/access.py.

    `division_code` is the department that named it. Null is the company's own,
    for titles that are nobody's department in particular.
    """

    __tablename__ = "positions"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(80))
    division_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RolePermission(TenantKey, Base):
    """One cell of the role x module matrix: this role may do `action` in `module_key`."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "role_key"], ["roles.org_id", "roles.key"], ondelete="CASCADE"),
    )

    role_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    module_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    action: Mapped[str] = mapped_column(String(16), primary_key=True)


class Assignment(TenantRow, Base):
    """Gives a person a role in a module, over a scope, inside one company.

    module_key is a module key or "*" (every module). The scope narrows from
    everything (no division) to a whole division (division only) to one team
    (division + subdivision) to one location under it (+ headquarters). Each
    level is only ever stored with the one above it; the check constraints and
    the composite foreign keys enforce that. The person must be a member of the
    company.

    Not every team has headquarters, so most people stop at subdivision. The
    ones who do sit at one are placed there and see that location's records,
    which is what "dispensed to a headquarters" means.
    """

    __tablename__ = "assignments"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "user_id"], ["memberships.org_id", "memberships.user_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["org_id", "role_key"], ["roles.org_id", "roles.key"]),
        ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),
        ForeignKeyConstraint(
            ["org_id", "division_code", "subdivision_code"],
            ["subdivisions.org_id", "subdivisions.division_code", "subdivisions.code"],
        ),
        ForeignKeyConstraint(
            ["org_id", "division_code", "subdivision_code", "headquarters_code"],
            [
                "headquarters.org_id",
                "headquarters.division_code",
                "headquarters.subdivision_code",
                "headquarters.code",
            ],
        ),
        CheckConstraint(
            "subdivision_code IS NULL OR division_code IS NOT NULL",
            name="subdivision_needs_division",
        ),
        CheckConstraint(
            "headquarters_code IS NULL OR subdivision_code IS NOT NULL",
            name="headquarters_needs_subdivision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    role_key: Mapped[str] = mapped_column(String(40))
    module_key: Mapped[str] = mapped_column(String(32))
    division_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subdivision_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    headquarters_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[Profile] = relationship(back_populates="assignments", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(viewonly=True)


class SessionRecord(TenantRow, Base):
    """One signing-in, in one company. Every token names it (`sid`), including
    the ones handed on to other apps; ending it ends them all."""

    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("org_id", "id", name="session_in_company"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when a Developer Admin is looking through this person's eyes rather
    # than signing in as themselves (app/platform.py). The session resolves as
    # the person -- same screens, same scopes -- but nothing can be changed
    # through it, and the audit log names who was really driving.
    viewed_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, default=None
    )


class PlatformSession(Base):
    """One signing-in that belongs to no company.

    A Developer Admin is not in any company (app/platform.py), so their session
    cannot be a row in `sessions`, which is walled per company by design. It is
    its own table rather than a nullable org_id: a session with no company is a
    different thing, not a company session missing a field, and keeping them
    apart means nothing can accidentally read one as the other."""

    __tablename__ = "platform_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SsoCode(TenantRow, Base):
    """A one-time code that hands a signed-in session to another app (60 seconds, single use)."""

    __tablename__ = "sso_codes"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "session_id"], ["sessions.org_id", "sessions.id"], ondelete="CASCADE"),
    )

    # sha256 of the code; the code itself is only ever in the redirect.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("sso_clients.id", ondelete="CASCADE"))
    session_id: Mapped[str] = mapped_column(String(36))
    redirect_uri: Mapped[str] = mapped_column(String(500))
    # PKCE (S256): only whoever started the sign-in can swap the code.
    code_challenge: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- price book ------------------------------------------------------------------


class PriceType(TenantKey, Base):
    """A kind of price: SRP, Patient's Price, Special Price... Switched off, never deleted.

    `entry` says where the amount comes from: "list" is the product's price
    kept in Inventory, "entered" is typed by the rep on the quote (a negotiated
    Special Price).
    """

    __tablename__ = "price_types"
    __table_args__ = (CheckConstraint("entry IN ('list', 'entered')", name="price_type_entry"),)

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    entry: Mapped[str] = mapped_column(String(16), default="list")
    requires_notes: Mapped[bool] = mapped_column(default=False)
    needs_approval: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class DivisionPricing(TenantKey, Base):
    """How one division prices its quotes. Set by Admins in Settings."""

    __tablename__ = "division_pricing"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),
        CheckConstraint(
            "discount_approval_bp >= 0 AND discount_approval_bp <= 10000", name="discount_approval_range"
        ),
    )

    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    # False for a division that quotes with notes only (BID).
    uses_price_list: Mapped[bool] = mapped_column(default=True)
    # DSWD, PCSO... pay with a guarantee letter. Not every division takes them.
    allows_guarantee_letters: Mapped[bool] = mapped_column(default=True)
    # Manual discounts above this share of a quote's value need Finance approval.
    discount_approval_bp: Mapped[int] = mapped_column(Integer, default=1000)

    price_types: Mapped[list["DivisionPriceType"]] = relationship(cascade="all, delete-orphan")


class DivisionPriceType(TenantKey, Base):
    """A price type a division may quote with. `rule` "with_rx" means only, and
    always, when the quote has a prescription (B2C's Doctor's Price)."""

    __tablename__ = "division_price_types"
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "division_code"], ["division_pricing.org_id", "division_pricing.division_code"]
        ),
        ForeignKeyConstraint(["org_id", "price_type_code"], ["price_types.org_id", "price_types.code"]),
        CheckConstraint("rule IN ('always', 'with_rx')", name="division_price_type_rule"),
    )

    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    rule: Mapped[str] = mapped_column(String(16), default="always")


class GuaranteeLetterIssuer(TenantKey, Base):
    """Who issues guarantee letters (DSWD, PCSO...). Switched off, never deleted."""

    __tablename__ = "gl_issuers"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Product(TenantRow, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("org_id", "code", name="product_code_per_company"),
        UniqueConstraint("org_id", "id", name="product_in_company"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    generic_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(60), nullable=True)
    form: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # What one unit is: "box of 30 tablets", "bottle 60 mL".
    unit: Mapped[str] = mapped_column(String(60))
    # What this company's own product fields hold for it (see CustomField).
    # generic_name, strength and form above are the pharma ones, kept as columns
    # until every screen reads them from here instead.
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    prices: Mapped[list["ProductPrice"]] = relationship(cascade="all, delete-orphan")


class ProductPrice(TenantRow, Base):
    __tablename__ = "product_prices"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "product_id"], ["products.org_id", "products.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["org_id", "price_type_code"], ["price_types.org_id", "price_types.code"]),
        CheckConstraint("amount_centavos >= 0", name="product_price_not_negative"),
    )

    product_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    amount_centavos: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TeamPriceType(TenantKey, Base):
    """Which price types one team quotes with. A team with no rows here follows
    its division's list, which is what every team does until its lead changes it."""

    __tablename__ = "team_price_types"
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "division_code", "subdivision_code"],
            ["subdivisions.org_id", "subdivisions.division_code", "subdivisions.code"],
        ),
        ForeignKeyConstraint(["org_id", "price_type_code"], ["price_types.org_id", "price_types.code"]),
    )

    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    subdivision_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    set_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TeamPrice(TenantKey, Base):
    """A price one team set for itself, over the company's. No row means the
    company's price stands, which is why a team that sets nothing prices exactly
    as it always did. Set by the team's lead (the "prices" action)."""

    __tablename__ = "team_prices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "division_code", "subdivision_code"],
            ["subdivisions.org_id", "subdivisions.division_code", "subdivisions.code"],
        ),
        ForeignKeyConstraint(["org_id", "product_id"], ["products.org_id", "products.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["org_id", "price_type_code"], ["price_types.org_id", "price_types.code"]),
        CheckConstraint("amount_centavos >= 0", name="team_price_not_negative"),
    )

    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    subdivision_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    price_type_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    amount_centavos: Mapped[int] = mapped_column(Integer)
    set_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Promo(TenantRow, Base):
    """A promo or discount a rep can put on a quote line.

    percent:     percent_bp off the line
    amount:      amount_centavos off each unit
    free_goods:  every buy_qty units bought, free_qty more free
    tiered:      the highest tier the quantity reaches (promo_tiers)
    """

    __tablename__ = "promos"
    __table_args__ = (
        UniqueConstraint("org_id", "id", name="promo_in_company"),
        CheckConstraint("kind IN ('percent', 'amount', 'free_goods', 'tiered')", name="promo_kind"),
        CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="promo_dates"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))
    percent_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buy_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    free_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # True: every product. False: only the products in promo_products.
    all_products: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    products: Mapped[list["PromoProduct"]] = relationship(cascade="all, delete-orphan")
    divisions: Mapped[list["PromoDivision"]] = relationship(cascade="all, delete-orphan")
    tiers: Mapped[list["PromoTier"]] = relationship(cascade="all, delete-orphan", order_by="PromoTier.min_qty")


class PromoProduct(TenantRow, Base):
    __tablename__ = "promo_products"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "promo_id"], ["promos.org_id", "promos.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["org_id", "product_id"], ["products.org_id", "products.id"], ondelete="CASCADE"),
    )

    promo_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), primary_key=True)


class PromoDivision(TenantRow, Base):
    __tablename__ = "promo_divisions"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "promo_id"], ["promos.org_id", "promos.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),
    )

    promo_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)


class RetentionRule(TenantKey, Base):
    """When a division's customers count as at risk, then lost, with no quote. Set in Settings -> Retention."""

    __tablename__ = "retention_rules"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),
        CheckConstraint("at_risk_days >= 1 AND lost_days > at_risk_days AND lost_days <= 730", name="retention_days"),
    )

    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    at_risk_days: Mapped[int] = mapped_column(Integer, default=45)
    lost_days: Mapped[int] = mapped_column(Integer, default=90)


class CompanyGoal(TenantKey, Base):
    """Whether a company tracks one of the goals Orbit knows how to work out
    (app/goals.py). No row means it does: a company that has never opened the
    screen sees all of them, as it always did."""

    __tablename__ = "company_goals"

    goal: Mapped[str] = mapped_column(String(40), primary_key=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class GoalTarget(TenantKey, Base):
    """A division's target for one goal (see app/goals.py). Absent: the goal's default."""

    __tablename__ = "goal_targets"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),
        CheckConstraint("target >= 0", name="goal_target_not_negative"),
    )

    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    goal: Mapped[str] = mapped_column(String(40), primary_key=True)
    # In the goal's unit: basis points, a count, centavos, or days.
    target: Mapped[int] = mapped_column(Integer)


class PromoTier(TenantRow, Base):
    __tablename__ = "promo_tiers"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "promo_id"], ["promos.org_id", "promos.id"], ondelete="CASCADE"),
        CheckConstraint("min_qty > 0 AND percent_bp > 0 AND percent_bp <= 10000", name="promo_tier_values"),
    )

    promo_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    min_qty: Mapped[int] = mapped_column(Integer, primary_key=True)
    percent_bp: Mapped[int] = mapped_column(Integer)


class Bundle(TenantRow, Base):
    """A named set of products sold at one price: "Starter Pack, 2 x Amoxicillin
    + 1 x Paracetamol, P1,800".

    Kept beside promos in Inventory because a person thinks of both as "the
    thing that makes this cost less", but it is not one: a promo is picked on
    top of a product line, a bundle instead of a product, and a bundle's
    products carry how many of each are in the set.

    `as_one_line` decides what the customer reads, not what anything costs. On
    it, the quote shows one line for the set; off it, the set's price is shared
    across its items (app/bundles.py). Either way the totals are the same, so a
    company can switch a bundle over without re-pricing anything.
    """

    __tablename__ = "bundles"
    __table_args__ = (
        UniqueConstraint("org_id", "id", name="bundle_in_company"),
        UniqueConstraint("org_id", "code", name="bundle_code_in_company"),
        CheckConstraint("price_centavos > 0", name="bundle_price"),
        CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="bundle_dates"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    price_centavos: Mapped[int] = mapped_column(Integer)
    as_one_line: Mapped[bool] = mapped_column(default=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list["BundleItem"]] = relationship(cascade="all, delete-orphan", order_by="BundleItem.sort_order")
    divisions: Mapped[list["BundleDivision"]] = relationship(cascade="all, delete-orphan")


class BundleItem(TenantRow, Base):
    """One product in a bundle, and how many of it the set contains."""

    __tablename__ = "bundle_items"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "bundle_id"], ["bundles.org_id", "bundles.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["org_id", "product_id"], ["products.org_id", "products.id"], ondelete="CASCADE"),
        CheckConstraint("qty > 0", name="bundle_item_qty"),
    )

    bundle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class BundleDivision(TenantRow, Base):
    __tablename__ = "bundle_divisions"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "bundle_id"], ["bundles.org_id", "bundles.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),
    )

    bundle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    division_code: Mapped[str] = mapped_column(String(32), primary_key=True)


class AuditEntry(TenantRow, Base):
    """Who changed what, and when. Field names only, never their values."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    # None when it wasn't a person (an API key, a scheduled job).
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(200), default="")
    fields: Mapped[list[str]] = mapped_column(JSON, default=list)


class ApiKey(TenantRow, Base):
    """Lets a program (not a person) call a few endpoints for one company, e.g.
    the Orders app's nightly recycle-bin job reading the order rules.
    The key is `orbit_<id>_<secret>`; only the secret's sha256 is kept."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    secret_hash: Mapped[str] = mapped_column(String(64))
    # What it may do, e.g. ["orders:config"].
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- order settings (the Orders app reads these through /orders-api) --------------------

ORDER_LIST_KINDS = ("payment_method", "payment_term", "source", "delivery_method", "invoicing_entity", "field_section")
# The pick-lists that shape the records themselves, rather than an order.
RECORD_LIST_KINDS = ("customer_kind", "activity_kind", "outcome")
LIST_KINDS = (*ORDER_LIST_KINDS, *RECORD_LIST_KINDS)
ORDER_FIELD_TYPES = ("text", "textarea", "number", "date", "choice")


class ListItem(TenantKey, Base):
    """One choice in one of a company's pick-lists: a payment method, a kind of
    customer, how a call went. Every list a company can change lives here, told
    apart by `kind` (see app/lists.py). Switched off, never deleted, so records
    that already carry the value keep making sense."""

    __tablename__ = "list_items"
    __table_args__ = (CheckConstraint("kind IN (" + ", ".join(f"'{k}'" for k in LIST_KINDS) + ")", name="list_kind"),)

    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    # An icon name from the frontend's registry; only some lists show icons.
    icon: Mapped[str | None] = mapped_column(String(40), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


FIELD_SUBJECTS = ("order", "product", "customer")


class CustomField(TenantKey, Base):
    """An extra field a company put on one of its records, beyond the ones every
    company has. `subject` says which record it belongs to.

    This is how an industry's own words get in without a deployment: a pharmacy
    adds Generic name, Strength and Form to its products; a machinery dealer
    adds Model and Warranty instead."""

    __tablename__ = "custom_fields"
    __table_args__ = (
        CheckConstraint("type IN ('text', 'textarea', 'number', 'date', 'choice')", name="custom_field_type"),
        CheckConstraint("subject IN ('order', 'product', 'customer')", name="custom_field_subject"),
    )

    subject: Mapped[str] = mapped_column(String(16), primary_key=True, default="order")
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    # Which part of the form it sits in, by the code of a `field_section` list
    # item. None means the last part, so a field is never lost off the form.
    section: Mapped[str | None] = mapped_column(String(60), default=None)
    label: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(16), default="text")
    required: Mapped[bool] = mapped_column(default=False)
    # The choices, for a "choice" field.
    options: Mapped[list[str]] = mapped_column(JSON, default=list)
    help: Mapped[str] = mapped_column(String(200), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class PricingSettings(TenantKey, Base):
    """The company's selling defaults, as against a division's pricing rules
    (DivisionPricing) or a team's own prices. One row per company.

    Only defaults live here: things a new row starts as, which whoever makes
    that row can still change. Set in Settings -> Pricing.
    """

    __tablename__ = "pricing_settings"

    # Which way a newly added bundle starts: one line on the quote, or its items.
    bundles_as_one_line: Mapped[bool] = mapped_column(default=True)


class OrderSettings(TenantKey, Base):
    """The company's order rules. One row per company (its key is the company)."""

    __tablename__ = "order_settings"
    __table_args__ = (
        CheckConstraint("large_order_centavos >= 0", name="large_order_not_negative"),
        CheckConstraint("recycle_days >= 1 AND recycle_days <= 365", name="recycle_days_range"),
    )

    # Open orders from this amount up get a second look before payment is verified.
    large_order_centavos: Mapped[int] = mapped_column(Integer, default=10_000_000)
    # Deleted orders wait this long in the recycle bin before they're gone for good.
    recycle_days: Mapped[int] = mapped_column(Integer, default=30)


# The tables shared by every company; every other table carries org_id.
# Tables that belong to the platform rather than to any one company, so a
# company's export holds no part of them.
SHARED_TABLES = frozenset(
    {
        "organizations",
        "profiles",
        "profile_photos",
        "local_credentials",
        "platform_admins",
        "platform_sessions",
        "sso_clients",
    }
)
