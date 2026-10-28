"""Finance's tables: its own accounts (nobody signed in here exists in any
other Bishnoi One app), tax, and the funds released to other apps' people.

Every table's name starts with nbfi_ (Finance), so it is plain which app a
table belongs to, whatever database it ends up in. Changes to them go through
a migration (migrations/versions)."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    FetchedValue,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Role(Base):
    __tablename__ = "nbfi_roles"

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
    __tablename__ = "nbfi_role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("nbfi_roles.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)

    role: Mapped[Role] = relationship(back_populates="grants")


class User(Base):
    __tablename__ = "nbfi_users"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (CheckConstraint("role IN ('admin', 'member')", name="user_role"), Index("nbfi_users_no", "no", unique=True),)

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
    # What they may do: their role's permissions (app/permissions.py).
    role_id: Mapped[str] = mapped_column(ForeignKey("nbfi_roles.id"), index=True)
    # Admin or member, from before roles (migration 0006). No longer read; kept
    # filled so the table didn't have to be rebuilt to drop it.
    legacy_role: Mapped[str] = mapped_column("role", String(16), default="member")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Every session started before this ends (see deps.current_user).
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Their Bishnoi One account on the platform, once they have signed in with it (app/platform_pass.py).
    platform_identity_id: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)
    # The calendar, switched on for this person by an Administrator (migration 0014).
    calendar_on: Mapped[bool] = mapped_column(default=False)

    role: Mapped[Role] = relationship(lazy="joined")

    def __init__(self, **kwargs):
        # role="admin" or "member", as accounts were made before roles: the
        # Administrator or Finance Staff role. A Role, or role_id, as they are now.
        from app.permissions import ROLE_ADMIN_ID, ROLE_STAFF_ID

        given = kwargs.pop("role", None)
        if isinstance(given, Role):
            kwargs["role"] = given
        elif "role_id" not in kwargs:
            kwargs["role_id"] = ROLE_ADMIN_ID if given == "admin" else ROLE_STAFF_ID
        admin = kwargs.get("role_id") == ROLE_ADMIN_ID or (isinstance(given, Role) and given.is_system)
        kwargs.setdefault("legacy_role", "admin" if admin else "member")
        super().__init__(**kwargs)


class AuditEntry(Base):
    """The activity log: who changed what, and when. Names the fields that
    changed, never their values. A marketing request's own steps are also kept as
    its events (FundEvent)."""

    __tablename__ = "nbfi_audit_log"

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
    # The Revenue District Office the company is registered under (e.g. "050"), and the month its
    # fiscal year ends (12: a calendar year): on every BIR form and summary list (app/bir_reports.py).
    rdo_code: Mapped[str | None] = mapped_column(String(3), default=None)
    fiscal_month_end: Mapped[int] = mapped_column(Integer, default=12)
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
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (CheckConstraint(f"type IN {ACCOUNT_TYPES}", name="account_type"), Index("nbfi_accounts_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # The account it sits under, as Oojeema's chart groups them (e.g. 6915-001 Provision
    # for Expired Medicines under 6915-000 Loss on Expired Medicines). Migration 0017.
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    # An asset or liability used or due within a year ("current") or later ("non_current"), for
    # working capital and the current and quick ratios (app/management.py, migration 0023). None:
    # worked out from its name.
    term: Mapped[str | None] = mapped_column(String(12), default=None)


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
    # Where an issued invoice posts: what customers owe, the sale, and the tax on it.
    receivables_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    sales_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    output_tax_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    # Where a recorded supplier bill posts (migration 0017): what's owed to suppliers, the VAT
    # on purchases, and the tax withheld from them for the BIR.
    payables_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    input_tax_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    withholding_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    # Creditable withholding a customer deducted from a payment (their Form 2307): credited against our income tax.
    cwt_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    # The cost of goods sold, booked with each invoice from Inventory's costs (migration 0024): the
    # expense, and the stock it comes out of. Either unset: invoices book no cost.
    cogs_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    inventory_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)


class JournalEntry(Base):
    """One entry: a date, what it's for, and its lines."""

    __tablename__ = "nbfi_journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    memo: Mapped[str] = mapped_column(String(300))
    reference: Mapped[str | None] = mapped_column(String(80), default=None)
    # manual: written by Finance. fund: posted by a marketing request's step.
    source: Mapped[str] = mapped_column(String(10), default="manual")
    fund_request_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_fund_requests.id", ondelete="SET NULL"), index=True, default=None)
    # The entry this one reverses, or that reversed this one.
    reverses_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), default=None)
    reversed_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), default=None)
    posted_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Approved entries count in the books; one typed by hand waits for someone who
    # may approve entries (not whoever posted it), and a rejected one never counts
    # (migration 0013). Entries a fund step or an invoice makes are approved as posted.
    status: Mapped[str] = mapped_column(String(10), default="approved", index=True)
    posted_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    decided_by: Mapped[str | None] = mapped_column(String(120), default=None)
    decided_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    rejected_reason: Mapped[str | None] = mapped_column(String(300), default=None)

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
    # The bank reconciliation that found it on the statement (cleared); None while it hasn't shown up there.
    reconciliation_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_bank_reconciliations.id", ondelete="SET NULL"), index=True, default=None)

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


# --- invoices: sales invoices to customers, numbered from the BIR's authority -------------
#
# An invoice is a draft until it's issued: then it takes the next number of
# its series, its amounts are worked out by the tax engine and kept as they
# were, and it posts to the ledger (what the customer owes, the sale, the tax).
# An issued invoice is never edited or deleted: it's voided, which keeps the
# number and posts the reversal, as the BIR expects every number accounted for.

INVOICE_STATUSES = ("draft", "issued", "void")


class InvoiceSeries(Base):
    """A run of invoice numbers the BIR authorized (the Authority to Print, or
    the system's permit): numbers are used in order and never past the last."""

    __tablename__ = "nbfi_invoice_series"
    __table_args__ = (CheckConstraint("first_number <= last_number", name="series_range"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    # Printed before the number: "SI-" gives SI-000123.
    prefix: Mapped[str] = mapped_column(String(10), default="")
    digits: Mapped[int] = mapped_column(Integer, default=6)
    first_number: Mapped[int] = mapped_column(Integer)
    last_number: Mapped[int] = mapped_column(Integer)
    next_number: Mapped[int] = mapped_column(Integer)
    atp_number: Mapped[str] = mapped_column(String(40))
    atp_date: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def left(self) -> int:
        return max(0, self.last_number - self.next_number + 1)


class Invoice(Base):
    __tablename__ = "nbfi_invoices"
    __table_args__ = (CheckConstraint("status IN ('draft', 'issued', 'void')", name="invoice_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    series_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_invoice_series.id"), default=None)
    # Given when it's issued; a voided invoice keeps it.
    number: Mapped[str | None] = mapped_column(String(30), unique=True, default=None)
    # The customer: the CRM's, when picked from it, and as the invoice states them.
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_tin: Mapped[str | None] = mapped_column(String(20), default=None)
    customer_address: Mapped[str | None] = mapped_column(String(300), default=None)
    # Whose sale it is: the CRM's salesperson (the customer's owner when picked from the CRM).
    # The CRM scores its people from these; none: it counts for nobody.
    salesperson_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    salesperson_name: Mapped[str | None] = mapped_column(String(120), default=None)
    # The salesperson's division and team on the company's org chart when the invoice was made
    # (migration 0025): revenue and margin by division. None: not placed, or not from the CRM.
    division_id: Mapped[str | None] = mapped_column(String(36), default=None)
    division_name: Mapped[str | None] = mapped_column(String(120), default=None)
    team_id: Mapped[str | None] = mapped_column(String(36), default=None)
    team_name: Mapped[str | None] = mapped_column(String(120), default=None)
    # Who is buying, as the tax engine reads it: regular, senior citizen, PWD...
    treatment: Mapped[str] = mapped_column(String(20), default="regular")
    buyer_id_number: Mapped[str | None] = mapped_column(String(40), default=None)
    invoice_date: Mapped[date] = mapped_column(Date)
    terms_days: Mapped[int] = mapped_column(Integer, default=30)
    reference: Mapped[str | None] = mapped_column(String(80), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    prices_include_tax: Mapped[bool | None] = mapped_column(default=None)
    # The lines as entered: [{description, ref, quantity, unitPriceCentavos, discountCentavos, category, reliefEligible}].
    lines: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # Kept as issued: the tax engine's answer, for printing it the same forever.
    computed: Mapped[dict | None] = mapped_column(JSON, default=None)
    # What its goods cost us, booked when it's issued (migration 0024): the total, and each line's
    # cost per unit as Inventory gave it (None: not known, by its item code).
    cost_centavos: Mapped[int] = mapped_column(Integer, default=0)
    line_costs: Mapped[list | None] = mapped_column(JSON, default=None)
    total_centavos: Mapped[int] = mapped_column(Integer, default=0)
    tax_centavos: Mapped[int] = mapped_column(Integer, default=0)
    paid_centavos: Mapped[int] = mapped_column(Integer, default=0)
    entry_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(120))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    issued_by: Mapped[str | None] = mapped_column(String(120), default=None)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    voided_by: Mapped[str | None] = mapped_column(String(120), default=None)
    void_reason: Mapped[str | None] = mapped_column(String(300), default=None)
    # The cancelled invoice this one replaces (cancel and reissue: Rommel Q20; migration
    # 0016). At most one replacement each; a deleted draft frees it. Not printed.
    replaces_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_invoices.id", ondelete="SET NULL"), unique=True, default=None)

    series: Mapped[InvoiceSeries | None] = relationship(lazy="joined")
    payments: Mapped[list["InvoicePayment"]] = relationship(
        back_populates="invoice", order_by="InvoicePayment.paid_on", cascade="all, delete-orphan", lazy="selectin"
    )


class InvoicePayment(Base):
    """Money received against an invoice. Posted as it's recorded (cash in,
    receivables down); one recorded by mistake is taken off, which posts the
    reversal and keeps the line, marked, so the story stays whole."""

    __tablename__ = "nbfi_invoice_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("nbfi_invoices.id", ondelete="CASCADE"), index=True)
    paid_on: Mapped[date] = mapped_column(Date)
    amount_centavos: Mapped[int] = mapped_column(Integer)
    # cash, bank, ewallet, check: the money account it lands in (Default accounts).
    method: Mapped[str] = mapped_column(String(10))
    reference: Mapped[str | None] = mapped_column(String(80), default=None)
    # What the customer withheld from this payment and paid the BIR for us (their Form 2307):
    # it settles the invoice as much as cash does. Its ATC ("WC158") and the certificate's reference.
    cwt_centavos: Mapped[int] = mapped_column(Integer, default=0)
    cwt_atc: Mapped[str | None] = mapped_column(String(8), default=None)
    cwt_certificate: Mapped[str | None] = mapped_column(String(60), default=None)
    entry_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), default=None)
    recorded_by: Mapped[str] = mapped_column(String(120))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    removed_by: Mapped[str | None] = mapped_column(String(120), default=None)

    invoice: Mapped[Invoice] = relationship(back_populates="payments")


class Notification(Base):
    """Something waiting on one person, or done to their work: shown under the
    bell until they've read it (app/notify.py)."""

    __tablename__ = "nbfi_notifications"
    __table_args__ = (Index("nbfi_notifications_inbox", "user_id", "read_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbfi_users.id", ondelete="CASCADE"))
    # What happened, e.g. "entry.waiting", "fund.to_release": for icons and tests.
    kind: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(String(300))
    # The page it's about, inside Finance (e.g. /ledger/entries/<id>).
    link: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


REPEATS = ("none", "monthly", "quarterly", "yearly", "twice_monthly")


class CalendarEvent(Base):
    """Something on one person's calendar (app/calendar_events.py): a deadline, a cut-off, a
    monthly chore. Theirs alone unless shared; it can repeat, and remind them some
    working days before. Decided 2026-10-22 (Plans/Plan - Finance calendar)."""

    __tablename__ = "nbfi_calendar_events"
    __table_args__ = (CheckConstraint(f"repeat IN {REPEATS}", name="calendar_repeat"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("nbfi_users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(String(1000), default=None)
    starts_on: Mapped[date] = mapped_column(Date)
    # "14:30"; none: all day.
    at_time: Mapped[str | None] = mapped_column(String(5), default=None)
    # none, monthly (same day), quarterly, yearly, twice_monthly (the 15th and the last day).
    repeat: Mapped[str] = mapped_column(String(16), default="none")
    until: Mapped[date | None] = mapped_column(Date, default=None)
    # Working days before each date to remind (0: on the day); none: no reminder.
    remind_days: Mapped[int | None] = mapped_column(Integer, default=None)
    # A page inside Finance it's about, e.g. /bir/sales-dat.
    link: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(lazy="joined")
    shares: Mapped[list["CalendarShare"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    done: Mapped[list["CalendarDone"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class CalendarShare(Base):
    """Someone else who sees an event (and can mark it done); only the owner edits it."""

    __tablename__ = "nbfi_calendar_shares"

    event_id: Mapped[str] = mapped_column(ForeignKey("nbfi_calendar_events.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbfi_users.id", ondelete="CASCADE"), primary_key=True, index=True)

    user: Mapped[User] = relationship(lazy="joined")


class CalendarDone(Base):
    """One date of an event, marked done: it stops reminding."""

    __tablename__ = "nbfi_calendar_done"

    event_id: Mapped[str] = mapped_column(ForeignKey("nbfi_calendar_events.id", ondelete="CASCADE"), primary_key=True)
    occurs_on: Mapped[date] = mapped_column(Date, primary_key=True)
    done_by: Mapped[str] = mapped_column(String(120))
    done_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    done_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Signature(Base):
    """A person's e-signature (app/signatures.py): set by them on their account page,
    drawn or uploaded, black on transparent. Replaced or removed ones are kept, so
    documents signed with them still show them. Decided 2026-10-22 (Plans/Plan - E-signatures)."""

    __tablename__ = "nbfi_signatures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbfi_users.id", ondelete="CASCADE"), index=True)
    # The cleaned image: a PNG, black ink on transparent.
    image: Mapped[bytes] = mapped_column(LargeBinary)
    # drawn or uploaded
    method: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # No longer the person's signature (replaced, or removed): kept for what it signed.
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    removed_by: Mapped[str | None] = mapped_column(String(120), default=None)


class SignedStep(Base):
    """A step someone did on a document, signed: who, which step, when, with which
    signature (none if they hadn't set one), and a fingerprint of the document's
    content at that moment (SHA-256)."""

    __tablename__ = "nbfi_signed_steps"
    __table_args__ = (Index("nbfi_signed_steps_record", "record_type", "record_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # journal_entry, fund_request
    record_type: Mapped[str] = mapped_column(String(20))
    record_id: Mapped[str] = mapped_column(String(36))
    # prepared, approved (journal); reviewed, settled (liquidation)
    step: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    signature_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_signatures.id", ondelete="SET NULL"), default=None)
    signer_name: Mapped[str] = mapped_column(String(120))
    signer_role: Mapped[str] = mapped_column(String(80))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    fingerprint: Mapped[str] = mapped_column(String(64))


# --- payables: suppliers and their bills (app/payables.py, migration 0017) -----------------
#
# A bill is a draft until it's recorded: then it posts to the books (the expense and the VAT
# on it, against what's owed the supplier and the tax withheld for the BIR) and is kept as
# recorded. A recorded bill is voided, never changed. Decided 2026-10-23 (Aubrey's answers;
# Plans/Plan - Suppliers, bills and chart import).

BILL_STATUSES = ("draft", "recorded", "void")


class Supplier(Base):
    """Someone the company buys from, with what every bill from them needs: their TIN,
    whether they charge VAT, and the tax usually withheld from them (Aubrey Q11)."""

    __tablename__ = "nbfi_suppliers"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbfi_suppliers_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    # How the supplier is shown (Zoho's "Display Name"); company_name: as registered (migration 0018).
    name: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str | None] = mapped_column(String(200), default=None)
    # The primary contact (Zoho's): Mr./Ms., first and last name.
    salutation: Mapped[str | None] = mapped_column(String(10), default=None)
    first_name: Mapped[str | None] = mapped_column(String(80), default=None)
    last_name: Mapped[str | None] = mapped_column(String(80), default=None)
    mobile: Mapped[str | None] = mapped_column(String(40), default=None)
    # Their bills post here instead of the default (e.g. 2101-000 AP - Trade vs 2102-000 AP - Non-Trade).
    payables_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    # Other people there: [{salutation, firstName, lastName, email, phone, mobile, designation}].
    contacts: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # 123-456-789, and the branch code (00000 for the head office). Zoho's "Company ID" (a
    # government or tax number) is this in the Philippines (decided 2026-10-23).
    tin: Mapped[str | None] = mapped_column(String(11), default=None)
    branch_code: Mapped[str | None] = mapped_column(String(5), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    vat_registered: Mapped[bool] = mapped_column(default=True)
    # The BIR's code for what's usually withheld (app/payables.py WITHHOLDING); none: nothing.
    withholding: Mapped[str | None] = mapped_column(String(10), default=None)
    terms_days: Mapped[int] = mapped_column(Integer, default=30)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    bank_name: Mapped[str | None] = mapped_column(String(80), default=None)
    bank_account_name: Mapped[str | None] = mapped_column(String(120), default=None)
    bank_account_number: Mapped[str | None] = mapped_column(String(40), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(120))

    files: Mapped[list["SupplierFile"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="SupplierFile.uploaded_at")


class SupplierFile(Base):
    """A supplier's papers, attached: their BIR 2303, accreditation, a contract (migration 0018)."""

    __tablename__ = "nbfi_supplier_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("nbfi_suppliers.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[str] = mapped_column(String(120))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Bill(Base):
    """A supplier's invoice, as the company owes it."""

    __tablename__ = "nbfi_bills"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (CheckConstraint(f"status IN {BILL_STATUSES}", name="bill_status"), Index("nbfi_bills_no", "no", unique=True))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("nbfi_suppliers.id"), index=True)
    # The supplier's own invoice number, as printed on their invoice.
    bill_number: Mapped[str] = mapped_column(String(60))
    bill_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    po_number: Mapped[str | None] = mapped_column(String(60), default=None)
    dr_number: Mapped[str | None] = mapped_column(String(60), default=None)
    # Checked against the purchase order and the delivery receipt (Aubrey Q7).
    checked_po: Mapped[bool] = mapped_column(default=False)
    checked_dr: Mapped[bool] = mapped_column(default=False)
    amounts_include_vat: Mapped[bool] = mapped_column(default=True)
    # The same bill in the other systems while they run side by side (Aubrey Q9, Q13).
    zoho_ref: Mapped[str | None] = mapped_column(String(60), default=None)
    oojeema_ref: Mapped[str | None] = mapped_column(String(60), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    # [{accountId, description, amountCentavos, vat, withholding}] as entered.
    lines: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # Worked out (app/payables.py), and kept as recorded.
    net_centavos: Mapped[int] = mapped_column(Integer, default=0)
    vat_centavos: Mapped[int] = mapped_column(Integer, default=0)
    withheld_centavos: Mapped[int] = mapped_column(Integer, default=0)
    total_centavos: Mapped[int] = mapped_column(Integer, default=0)
    payable_centavos: Mapped[int] = mapped_column(Integer, default=0)
    entry_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), default=None)
    # What released payment vouchers have paid on it, and the payables account it posted to
    # when recorded (vouchers take it off that same account). Migration 0019.
    paid_centavos: Mapped[int] = mapped_column(Integer, default=0)
    payables_account_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    # Where a draft stands in its approval (Aubrey's flow, 2026-10-23; migration 0020): none (being
    # made), to_approve (Malou; Cristal backup), to_check (Mel, only with tax withheld), returned.
    # It's posted (status recorded) only when it clears. Beside status, so that table is never rebuilt.
    stage: Mapped[str | None] = mapped_column(String(12), default=None, index=True)
    submitted_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    approved_by: Mapped[str | None] = mapped_column(String(120), default=None)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    checked_by: Mapped[str | None] = mapped_column(String(120), default=None)
    checked_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(120))
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    recorded_by: Mapped[str | None] = mapped_column(String(120), default=None)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    voided_by: Mapped[str | None] = mapped_column(String(120), default=None)
    void_reason: Mapped[str | None] = mapped_column(String(300), default=None)

    supplier: Mapped[Supplier] = relationship(lazy="joined")
    files: Mapped[list["BillFile"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="BillFile.uploaded_at")
    events: Mapped[list["BillEvent"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="BillEvent.id")


class BillEvent(Base):
    """What happened to a bill, in order: submitted, approved, returned (with why), checked, cleared, voided."""

    __tablename__ = "nbfi_bill_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("nbfi_bills.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(20))
    who: Mapped[str] = mapped_column(String(120))
    who_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    text: Mapped[str | None] = mapped_column(String(300), default=None)


class BillFile(Base):
    """The supplier's invoice, attached: a photo or a PDF (kept in nbfi_stored_files)."""

    __tablename__ = "nbfi_bill_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    bill_id: Mapped[str] = mapped_column(ForeignKey("nbfi_bills.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[str] = mapped_column(String(120))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- payment vouchers: paying suppliers' bills (app/routers/vouchers.py, migration 0019) -----
#
# Prepared for a supplier's bills ready to pay (one voucher, several bills, part of a bill
# allowed); Cristal releases it, which posts it (Dr each bill's payables account, Cr the account
# it's paid from). Returned with a reason, it goes back to whoever prepared it. Decided 2026-10-23
# (Plans/Plan - Payment vouchers; Cristal Q4, Q16; Aubrey Q12, Q14). The same day Aubrey moved the
# checks to the bill (migration 0020): to_check and to_approve, and checked_by and approved_by
# below, are no longer used, and stay only so the table is never rebuilt.

VOUCHER_STATUSES = ("draft", "returned", "to_check", "to_approve", "to_release", "released", "cancelled", "void")
# Not yet released or cancelled: what they hold of a bill is set aside, so it isn't paid twice.
OPEN_VOUCHERS = ("draft", "returned", "to_check", "to_approve", "to_release")


class PaymentVoucher(Base):
    __tablename__ = "nbfi_payment_vouchers"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (CheckConstraint(f"status IN {VOUCHER_STATUSES}", name="voucher_status"), Index("nbfi_payment_vouchers_no", "no", unique=True))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    # PV-202610-0001: the Hub's own voucher number.
    number: Mapped[str] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("nbfi_suppliers.id"), index=True)
    # bank (transfer), check, cash
    method: Mapped[str] = mapped_column(String(10), default="bank")
    # The bank or cash account it's paid from (an account under CASH in the chart).
    paid_from_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), default=None)
    total_centavos: Mapped[int] = mapped_column(Integer, default=0)
    # The same payment in the other systems (Aubrey Q9, Q13; step 6).
    oojeema_ref: Mapped[str | None] = mapped_column(String(60), default=None)
    zoho_ref: Mapped[str | None] = mapped_column(String(60), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    prepared_by: Mapped[str] = mapped_column(String(120))
    prepared_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    checked_by: Mapped[str | None] = mapped_column(String(120), default=None)
    checked_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    approved_by: Mapped[str | None] = mapped_column(String(120), default=None)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    released_by: Mapped[str | None] = mapped_column(String(120), default=None)
    released_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    # Set at release: when it was paid, and the bank's reference or the check's number and date.
    paid_on: Mapped[date | None] = mapped_column(Date, default=None)
    bank_reference: Mapped[str | None] = mapped_column(String(80), default=None)
    check_number: Mapped[str | None] = mapped_column(String(40), default=None)
    check_date: Mapped[date | None] = mapped_column(Date, default=None)
    entry_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    supplier: Mapped[Supplier] = relationship(lazy="joined")
    lines: Mapped[list["VoucherLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="VoucherLine.position")
    events: Mapped[list["VoucherEvent"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="VoucherEvent.id")
    files: Mapped[list["VoucherFile"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="VoucherFile.uploaded_at")


class VoucherLine(Base):
    """One bill a voucher pays, and how much of it."""

    __tablename__ = "nbfi_voucher_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voucher_id: Mapped[str] = mapped_column(ForeignKey("nbfi_payment_vouchers.id", ondelete="CASCADE"), index=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("nbfi_bills.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    amount_centavos: Mapped[int] = mapped_column(Integer)

    bill: Mapped[Bill] = relationship(lazy="joined")


class VoucherEvent(Base):
    """What happened to a voucher, in order: submitted, checked, returned (with why), approved, released..."""

    __tablename__ = "nbfi_voucher_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voucher_id: Mapped[str] = mapped_column(ForeignKey("nbfi_payment_vouchers.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(20))
    who: Mapped[str] = mapped_column(String(120))
    who_id: Mapped[str | None] = mapped_column(ForeignKey("nbfi_users.id", ondelete="SET NULL"), default=None)
    text: Mapped[str | None] = mapped_column(String(300), default=None)


class VoucherFile(Base):
    """Proof of payment, attached: the deposit slip, a photo of the check, the bank's confirmation."""

    __tablename__ = "nbfi_voucher_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    voucher_id: Mapped[str] = mapped_column(ForeignKey("nbfi_payment_vouchers.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[str] = mapped_column(String(120))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BankReconciliation(Base):
    """One bank statement matched against the books (decided 2026-10-24, from
    Oojeema): for a cash or bank account, up to the statement's date, which of
    the book's movements the bank shows (cleared), until the cleared balance
    equals the statement's ending balance. Finished, the cleared lines are marked
    and the next statement starts from this one's balance."""

    __tablename__ = "nbfi_bank_reconciliations"
    __table_args__ = (CheckConstraint("status IN ('open', 'done')", name="reconciliation_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("nbfi_accounts.id"), index=True)
    statement_date: Mapped[date] = mapped_column(Date)
    statement_balance_centavos: Mapped[int] = mapped_column(Integer)
    opening_balance_centavos: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(6), default="open", index=True)
    # While open: the journal lines ticked as on the statement.
    cleared: Mapped[list[int]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(120))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_by: Mapped[str | None] = mapped_column(String(120), default=None)

    account: Mapped[Account] = relationship(lazy="joined")


# Numbers on SQLite as records are saved (on Postgres the database gives them).
from app.numbering import numbered  # noqa: E402  (after the models it names)

numbered(User, Account, Supplier, Bill, PaymentVoucher)
