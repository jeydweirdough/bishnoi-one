"""Finance's tables: its own accounts (nobody signed in here exists in any
other Nabhi app), tax, and the funds released to other apps' people.

Every table's name starts with nbfi_ (Finance), so it is plain which app a
table belongs to, whatever database it ends up in. Changes to them go through
a migration (migrations/versions)."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    # Their Nabhi account on the platform, once they have signed in with it (app/platform_pass.py).
    platform_identity_id: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)


class PlatformPass(Base):
    """A pass from the platform already taken: each one works once. Kept until it would have expired."""

    __tablename__ = "nbfi_platform_passes"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


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


# --- funds: money released to people in other apps, and how it was spent ---------------------
#
# A salesperson asks for money in the CRM (a partnership dinner), their Team
# Lead approves it there, and it arrives here to be released. What happens
# next depends on whether it's liquidated: if it is, they send back what they
# spent, receipt by receipt; Finance checks each one, and what's left is
# either unused funds to hand back or an amount Finance reimburses.


class ExpenseCategory(Base):
    """What money was spent on, as Finance sorts it: a category (Food) is an
    expense account in the chart of accounts, and its sub-categories
    (Dining, Breakfast) say more about a receipt without an account of their
    own. Only a reimbursable category counts against the money released:
    anything else is the person's own, so it doesn't lower their unused funds or
    raise a reimbursement. A sub-category is its category's in both."""

    __tablename__ = "nbfi_expense_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Unique among its siblings (app/routers/funds.py checks), not everywhere:
    # Food › Other and Transportation › Other are both fine.
    name: Mapped[str] = mapped_column(String(80))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_expense_categories.id", ondelete="CASCADE"), index=True, default=None)
    # A category's account; None on a sub-category, which posts to its category's.
    account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    reimbursable: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    parent: Mapped["ExpenseCategory | None"] = relationship(remote_side="ExpenseCategory.id", lazy="joined", join_depth=1)
    account: Mapped["Account | None"] = relationship(lazy="joined")

    @property
    def top(self) -> "ExpenseCategory":
        """The category that holds the account and the reimbursable rule."""
        return self.parent or self

    @property
    def covered(self) -> bool:
        return self.top.reimbursable

    @property
    def label(self) -> str:
        return f"{self.parent.name} › {self.name}" if self.parent else self.name


# --- the ledger: a chart of accounts and a double-entry journal -------------------------------
#
# Every entry's debits equal its credits. A posted entry is never changed: a
# mistake is undone by reversing it (a new entry with the sides swapped).

ACCOUNT_TYPES = ("asset", "liability", "equity", "income", "expense")


class Account(Base):
    """One account of the chart: 1000 Cash on hand, 6100 Food."""

    __tablename__ = "nbfi_accounts"
    __table_args__ = (CheckConstraint(f"type IN {ACCOUNT_TYPES}", name="account_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LedgerSettings(Base):
    """Which accounts the fund steps post to. One row."""

    __tablename__ = "nbfi_ledger_settings"
    __table_args__ = (CheckConstraint("id = 1", name="one_ledger_settings"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Money given out ahead of spending, until it's accounted for.
    advances_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    # What the company owes someone who spent more than they were given.
    due_to_employees_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    # Where money goes out from and comes back to, by how it's handed over.
    cash_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    bank_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    ewallet_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    check_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)


class JournalEntry(Base):
    """One entry: a date, what it's for, and its lines."""

    __tablename__ = "nbfi_journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    memo: Mapped[str] = mapped_column(String(300))
    reference: Mapped[str | None] = mapped_column(String(80), default=None)
    # manual: written by Finance. fund: posted by a fund request's step.
    source: Mapped[str] = mapped_column(String(10), default="manual")
    fund_request_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_fund_requests.id", ondelete="SET NULL"), index=True, default=None)
    # The entry this one reverses, or that reversed this one.
    reverses_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), default=None)
    reversed_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), default=None)
    posted_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lines: Mapped[list["JournalLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="JournalLine.position")


class JournalLine(Base):
    """One side of an entry: an account, debited or credited."""

    __tablename__ = "nbfi_journal_lines"
    __table_args__ = (
        CheckConstraint("debit_centavos >= 0 AND credit_centavos >= 0 AND (debit_centavos = 0) <> (credit_centavos = 0)", name="one_side"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    account_id: Mapped[str] = mapped_column(ForeignKey("nbfi_accounts.id"), index=True)
    debit_centavos: Mapped[int] = mapped_column(Integer, default=0)
    credit_centavos: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(200), default=None)

    account: Mapped[Account] = relationship(lazy="joined")


FUND_STATUSES = ("to_release", "to_liquidate", "to_check", "to_return", "to_reimburse", "closed", "cancelled")


class FundRequest(Base):
    """One request, from the moment it was approved in the app it came from.
    Who asked, and who approved, are that app's people: kept here by name."""

    __tablename__ = "nbfi_fund_requests"
    __table_args__ = (
        CheckConstraint(f"status IN {FUND_STATUSES}", name="fund_status"),
        UniqueConstraint("source_app", "source_id", name="fund_from_source_once"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Where it came from: "crm", and the request's id and number there.
    source_app: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str] = mapped_column(String(36))
    number: Mapped[str] = mapped_column(String(30), index=True)
    requester_name: Mapped[str] = mapped_column(String(120))
    requester_email: Mapped[str] = mapped_column(String(254), index=True)
    team_name: Mapped[str | None] = mapped_column(String(80), default=None)
    purpose: Mapped[str] = mapped_column(String(80))
    details: Mapped[str | None] = mapped_column(Text, default=None)
    # Who it's for, when it's for a customer (the partner at the dinner).
    customer_name: Mapped[str | None] = mapped_column(String(200), default=None)
    needed_on: Mapped[date | None] = mapped_column(Date, default=None)
    # Whether receipts and unused funds come back after it's spent.
    liquidate: Mapped[bool] = mapped_column(default=True)
    requested_centavos: Mapped[int] = mapped_column(Integer)
    approved_centavos: Mapped[int] = mapped_column(Integer)
    approved_by_name: Mapped[str] = mapped_column(String(120))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approval_note: Mapped[str | None] = mapped_column(String(500), default=None)

    status: Mapped[str] = mapped_column(String(16), default="to_release", index=True)
    # The release: how much, how it was handed over, and when it's to be liquidated by.
    released_centavos: Mapped[int | None] = mapped_column(Integer, default=None)
    release_method: Mapped[str | None] = mapped_column(String(20), default=None)
    release_reference: Mapped[str | None] = mapped_column(String(80), default=None)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    released_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    liquidate_by: Mapped[date | None] = mapped_column(Date, default=None)
    # The liquidation: sent in, checked, and what it came to.
    liquidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    checked_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    # What was sent back to be fixed, the last time it was.
    sent_back_note: Mapped[str | None] = mapped_column(String(500), default=None)
    covered_centavos: Mapped[int | None] = mapped_column(Integer, default=None)
    return_due_centavos: Mapped[int] = mapped_column(Integer, default=0)
    returned_centavos: Mapped[int] = mapped_column(Integer, default=0)
    reimburse_due_centavos: Mapped[int] = mapped_column(Integer, default=0)
    reimbursed_centavos: Mapped[int] = mapped_column(Integer, default=0)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    expenses: Mapped[list["FundExpense"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", lazy="selectin", order_by="FundExpense.spent_on"
    )
    events: Mapped[list["FundEvent"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="FundEvent.id")
    # What it posted to the journal, in order.
    entries: Mapped[list["JournalEntry"]] = relationship(lazy="selectin", viewonly=True, order_by="JournalEntry.number")


class FundExpense(Base):
    """One thing the money was spent on, with its receipt."""

    __tablename__ = "nbfi_fund_expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(ForeignKey("nbfi_fund_requests.id", ondelete="CASCADE"), index=True)
    spent_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_expense_categories.id", ondelete="SET NULL"), default=None)
    amount_centavos: Mapped[int] = mapped_column(Integer)
    # The receipt (nbfi_stored_files), or why there isn't one.
    receipt_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    receipt_name: Mapped[str | None] = mapped_column(String(160), default=None)
    no_receipt_reason: Mapped[str | None] = mapped_column(String(300), default=None)
    # Finance's check: None until checked; False with the reason when refused.
    accepted: Mapped[bool | None] = mapped_column(default=None)
    refused_reason: Mapped[str | None] = mapped_column(String(300), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    request: Mapped[FundRequest] = relationship(back_populates="expenses")
    category: Mapped[ExpenseCategory | None] = relationship(lazy="joined")


class FundEvent(Base):
    """What happened to a request, in order: its record of the money."""

    __tablename__ = "nbfi_fund_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("nbfi_fund_requests.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # approved, released, expense, submitted, sent_back, checked, returned, reimbursed, closed, cancelled
    kind: Mapped[str] = mapped_column(String(20))
    who: Mapped[str] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(String(500))
    amount_centavos: Mapped[int | None] = mapped_column(Integer, default=None)


class StoredFile(Base):
    """An uploaded file (a receipt), kept in the database itself, so a host
    without a lasting disk (Vercel) keeps it all the same."""

    __tablename__ = "nbfi_stored_files"

    ref: Mapped[str] = mapped_column(String(32), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
