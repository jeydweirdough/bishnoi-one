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
    """Owed to suppliers at the end of the day, rebuilt from dated bills, payments and voids
    (app/payables_asof.py), not from what's paid now (corrected 2026-10-29)."""
    from app.payables_asof import total_owed_on
    return total_owed_on(db, on)


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
    # Step 17: expenses tagged on the chart of accounts, and new customers.
    addbacks: int = 0  # depreciation, amortisation, interest and income tax: added back for EBITDA
    fixed_costs: int | None = None  # None: no expense tagged fixed or variable yet
    variable_costs: int = 0
    sales_marketing: int | None = None
    new_customers: int = 0

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
    def ebitda(self) -> int:
        """Profit from the business itself: net profit with depreciation, amortisation, interest and income tax added back."""
        return self.net_profit + self.addbacks

    @property
    def equity(self) -> int:
        return self.position.assets - self.position.liabilities

    @property
    def return_on_equity(self) -> float | None:
        return self.ratio(self.net_profit, self.equity) if self.equity > 0 else None

    @property
    def debt_to_equity(self) -> float | None:
        return self.ratio(self.position.liabilities, self.equity) if self.equity > 0 else None

    @property
    def contribution_margin(self) -> float | None:
        """What each peso of revenue leaves after its variable costs."""
        return self.ratio(self.revenue - self.variable_costs, self.revenue) if self.fixed_costs is not None and self.revenue else None

    @property
    def break_even(self) -> int | None:
        """The revenue that covers the fixed costs: fixed costs ÷ contribution margin."""
        cm = self.contribution_margin
        return round(self.fixed_costs / cm) if cm and cm > 0 and self.fixed_costs is not None else None

    @property
    def acquisition_cost(self) -> int | None:
        """What winning one new customer cost: sales and marketing spend ÷ new customers."""
        return round(self.sales_marketing / self.new_customers) if self.sales_marketing is not None and self.new_customers else None

    @property
    def cash_cycle(self) -> float | None:
        parts = (self.days_to_collect, self.days_stock_sits, self.days_to_pay)
        return None if any(p is None for p in parts) else parts[0] + parts[1] - parts[2]


def tagged(db: Session, first: date, last: date) -> dict:
    """Expenses in the period by their tags on the chart of accounts (step 17)."""
    moves = bir.balances(db, start=first, end=last)
    out = {"addbacks": 0, "fixed": 0, "variable": 0, "sales_marketing": 0, "any_behaviour": False, "any_marketing": False}
    for a in db.scalars(select(Account).where(Account.type == "expense")):
        d, c = moves.get(a.id, (0, 0))
        spent = d - c
        if a.report_tag in ("depreciation", "amortisation", "interest", "income_tax"):
            out["addbacks"] += spent
        if a.report_tag == "sales_marketing":
            out["sales_marketing"] += spent
            out["any_marketing"] = True
        if a.cost_behaviour in ("fixed", "variable"):
            out[a.cost_behaviour] += spent
            out["any_behaviour"] = True
    return out


def new_customers(db: Session, first: date, last: date) -> int:
    """Customers whose first issued invoice falls in the period."""
    key = func.coalesce(Invoice.customer_id, func.lower(Invoice.customer_name))
    firsts = select(key.label("k"), func.min(Invoice.invoice_date).label("d")).where(Invoice.status == "issued").group_by(key).subquery()
    return int(db.scalar(select(func.count()).select_from(firsts).where(firsts.c.d >= first, firsts.c.d <= last)) or 0)


def figures(db: Session, first: date, last: date, zone: ZoneInfo) -> Figures:
    st = bir.income_statement(db, first, last)["totals"]
    p = position(db, last)
    t = tagged(db, first, last)
    cogs = cost_of_sales(db, first, last)
    return Figures(
        addbacks=t["addbacks"],
        fixed_costs=t["fixed"] if t["any_behaviour"] else None,
        # Cost of goods sold moves with sales: variable, unless its account is tagged otherwise.
        variable_costs=t["variable"] + (cogs if not _cogs_tagged(db) else 0),
        sales_marketing=t["sales_marketing"] if t["any_marketing"] else None,
        new_customers=new_customers(db, first, last),
        cogs=cogs,
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


def _cogs_tagged(db: Session) -> bool:
    from app.ledger import settings as posting_settings

    cogs = posting_settings(db).cogs_account_id
    a = db.get(Account, cogs) if cogs else None
    return bool(a and a.cost_behaviour)


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
