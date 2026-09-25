"""Finance's tables: its own accounts (nobody signed in here exists in any
other Nabhi app), and tax.

Every table's name starts with nbfi_ (Finance), so it is plain which app a
table belongs to, whatever database it ends up in. Changes to them go through
a migration (migrations/versions)."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "nbfi_users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'member')", name="user_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    # admin: runs this app's settings. member: uses it.
    role: Mapped[str] = mapped_column(String(16), default="member")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Every session started before this ends (see deps.current_user).
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SignInSession(Base):
    """One sign-in. The browser holds the token; only its hash is kept here."""

    __tablename__ = "nbfi_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbfi_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# --- tax --------------------------------------------------------------------------------


class TaxProfile(Base):
    """The company's tax registration, as its invoices state it. One row."""

    __tablename__ = "nbfi_tax_profile"
    __table_args__ = (CheckConstraint("id = 1", name="one_tax_profile"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Which country's pack applies (app/tax/packs).
    country: Mapped[str] = mapped_column(String(2), default="PH")
    # vat: VAT-registered. non_vat: not, so it pays percentage tax instead.
    regime: Mapped[str] = mapped_column(String(12), default="vat")
    registered_name: Mapped[str | None] = mapped_column(String(200), default=None)
    trade_name: Mapped[str | None] = mapped_column(String(200), default=None)
    # 123-456-789, and the branch code (00000 for the head office).
    tin: Mapped[str | None] = mapped_column(String(11), default=None)
    branch_code: Mapped[str] = mapped_column(String(5), default="00000")
    registered_address: Mapped[str | None] = mapped_column(String(300), default=None)
    # Whether catalogue prices already include VAT (as shelf prices do).
    prices_include_tax: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)


class TaxRate(Base):
    """One rate for one tax code, over the days it applies. A change in the law
    is a new row from its first day; the old row ends the day before, so a sale
    is always taxed at the rate of its own day."""

    __tablename__ = "nbfi_tax_rates"
    __table_args__ = (UniqueConstraint("country", "code", "valid_from", name="tax_rate_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(2))
    code: Mapped[str] = mapped_column(String(20), index=True)
    rate_bp: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, default=None)
    # pack: from the country pack's own table. admin: entered here.
    source: Mapped[str] = mapped_column(String(8), default="pack")
    # The law or circular it comes from.
    basis: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
