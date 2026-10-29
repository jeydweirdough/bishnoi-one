"""The figures a business manager reads (decided 2026-10-28, feature plan Track R): revenue,
profit and margin, return on assets, working capital, current and quick ratios, days to collect
and to pay, cash, and where cash is heading. Worked out from the books, invoices and bills
already here; fixed, so everyone reads the same number (app/routers/reports.py, group Management).

Current or long-term: working capital and the two ratios need to know which assets and
liabilities are current (used or due within a year). Each account says so (Account.term,
migration 0023); one that doesn't is worked out from its name, and the report says how many.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import bir_reports as bir
from app.models import Account, Bill, Invoice
from app.receivables_asof import total_owed_on

LONG_TERM = re.compile(
    r"property|plant|equipment|furniture|fixture|vehicle|building|land\b|leasehold|depreciation|amortization|investment|"
    r"long[- ]term|non[- ]?current|deferred tax|intangible|goodwill|security deposit|loan[s]? payable.*(long|non)",
    re.I,
)
STOCK = re.compile(r"inventor|merchandise|stock|goods", re.I)


def term_of(a: Account) -> tuple[str, bool]:
    """("current" or "non_current", whether it was worked out from the name)."""
    if a.term in ("current", "non_current"):
        return a.term, False
    return ("non_current" if LONG_TERM.search(a.name or "") else "current"), True


@dataclass
class Position:
    """The balance sheet's parts as of a day, in centavos."""

    assets: int = 0
    current_assets: int = 0
    stock: int = 0
    current_liabilities: int = 0
    liabilities: int = 0
    cash: int = 0
    guessed: int = 0


def position(db: Session, on: date) -> Position:
    sums = bir.balances(db, end=on)
    money = bir.money_accounts(db)
    p = Position()
    for a in db.scalars(select(Account).where(Account.type.in_(("asset", "liability")))):
        debit, credit = sums.get(a.id, (0, 0))
        amount = bir.signed(a, debit, credit)
        term, guessed = term_of(a)
        if amount and guessed:
            p.guessed += 1
        if a.type == "asset":
            p.assets += amount
            if term == "current":
                p.current_assets += amount
                if STOCK.search(a.name or ""):
                    p.stock += amount
            if a.id in money:
                p.cash += amount
        else:
            p.liabilities += amount
            if term == "current":
                p.current_liabilities += amount
    return p


def cost_of_sales(db: Session, first: date, last: date) -> int:
    """The cost of goods sold in the period: what was booked to its account (voids taken off),
    or, before that account is set, what the period's invoices cost."""
    from app.ledger import settings as posting

    cogs = posting(db).cogs_account_id
    if cogs:
        debit, credit = bir.balances(db, start=first, end=last).get(cogs, (0, 0))
        return debit - credit
    total = db.scalar(select(func.coalesce(func.sum(Invoice.cost_centavos), 0)).where(Invoice.status == "issued", Invoice.invoice_date >= first, Invoice.invoice_date <= last))
    return int(total or 0)


def inventory_value(db: Session, on: date, fallback: int) -> int:
    """Stock on hand in the books on the day: the inventory account's balance, or the accounts named
    like inventory when it isn't set."""
    from app.ledger import settings as posting

    stock = posting(db).inventory_account_id
    if not stock:
        return fallback
    debit, credit = bir.balances(db, end=on).get(stock, (0, 0))
    return debit - credit


def revenue(db: Session, first: date, last: date) -> int:
    """Invoiced sales in the period, without VAT."""
    total = db.scalar(
        select(func.coalesce(func.sum(Invoice.total_centavos - Invoice.tax_centavos), 0))
        .where(Invoice.status == "issued", Invoice.invoice_date >= first, Invoice.invoice_date <= last)
    )
    return int(total or 0)


def purchases(db: Session, first: date, last: date) -> int:
    """Supplier bills recorded in the period, without VAT."""
    total = db.scalar(select(func.coalesce(func.sum(Bill.net_centavos), 0)).where(Bill.status == "recorded", Bill.bill_date >= first, Bill.bill_date <= last))
    return int(total or 0)


def receivables(db: Session, on: date, zone: ZoneInfo) -> int:
    """Still owed by customers at the end of the day, rebuilt from dated payments,
    take-offs and voids (app/receivables_asof.py), not from what's paid now."""
    return total_owed_on(db, on, zone)


def payables(db: Session, on: date) -> int:
    """Still owed to suppliers on bills dated up to the day (at what's paid today)."""
    total = db.scalar(
        select(func.coalesce(func.sum(Bill.payable_centavos - Bill.paid_centavos), 0))
        .where(Bill.status == "recorded", Bill.bill_date <= on, Bill.paid_centavos < Bill.payable_centavos)
    )
    return int(total or 0)


@dataclass
class Figures:
    revenue: int
    income: int
    net_profit: int
    position: Position
    receivables: int
    payables: int
    purchases: int
    days: int
    cogs: int = 0
    inventory: int = 0

    def ratio(self, top: int, bottom: int) -> float | None:
        return top / bottom if bottom else None

    @property
    def net_margin(self) -> float | None:
        return self.ratio(self.net_profit, self.income)

    @property
    def return_on_assets(self) -> float | None:
        return self.ratio(self.net_profit, self.position.assets) if self.position.assets > 0 else None

    @property
    def working_capital(self) -> int:
        return self.position.current_assets - self.position.current_liabilities

    @property
    def current_ratio(self) -> float | None:
        return self.ratio(self.position.current_assets, self.position.current_liabilities)

    @property
    def quick_ratio(self) -> float | None:
        return self.ratio(self.position.current_assets - self.position.stock, self.position.current_liabilities)

    @property
    def days_to_collect(self) -> float | None:
        return self.receivables / self.revenue * self.days if self.revenue else None

    @property
    def days_to_pay(self) -> float | None:
        return self.payables / self.purchases * self.days if self.purchases else None

    @property
    def gross_profit(self) -> int:
        return self.revenue - self.cogs

    @property
    def gross_margin(self) -> float | None:
        return self.ratio(self.gross_profit, self.revenue) if self.cogs else None

    @property
    def days_stock_sits(self) -> float | None:
        return self.inventory / self.cogs * self.days if self.cogs and self.inventory > 0 else None

    @property
    def inventory_turnover(self) -> float | None:
        """Times a year stock sells and is replaced, at the period's pace."""
        return self.cogs * (365 / self.days) / self.inventory if self.cogs and self.inventory > 0 else None

    @property
    def cash_cycle(self) -> float | None:
        parts = (self.days_to_collect, self.days_stock_sits, self.days_to_pay)
        return None if any(p is None for p in parts) else parts[0] + parts[1] - parts[2]


def figures(db: Session, first: date, last: date, zone: ZoneInfo) -> Figures:
    st = bir.income_statement(db, first, last)["totals"]
    p = position(db, last)
    return Figures(
        cogs=cost_of_sales(db, first, last),
        inventory=inventory_value(db, last, p.stock),
        revenue=revenue(db, first, last),
        income=st["incomeCentavos"],
        net_profit=st["netCentavos"],
        position=p,
        receivables=receivables(db, last, zone),
        payables=payables(db, last),
        purchases=purchases(db, first, last),
        days=(last - first).days + 1,
    )


def previous(first: date, last: date) -> tuple[date, date]:
    """The period of the same length just before."""
    length = (last - first).days + 1
    return first - timedelta(days=length), first - timedelta(days=1)


def peso(centavos: int | None) -> str:
    """₱381K, ₱16.94M (the system's short amounts)."""
    if centavos is None:
        return "—"
    pesos = centavos / 100
    sign = "−" if pesos < 0 else ""
    v = abs(pesos)
    if v >= 1_000_000_000:
        return f"{sign}₱{v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{sign}₱{v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"{sign}₱{v / 1_000:.0f}K"
    return f"{sign}₱{v:,.2f}"
