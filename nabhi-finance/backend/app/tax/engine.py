"""The tax engine: turns a sale's lines into what an invoice shows.

It knows no country. A country's rules come from its pack (app/tax/packs):
which tax code a line gets, for which buyer, and any relief (the Philippines'
senior citizen and PWD discount, for one). Rates come from outside too,
dated, so a sale is taxed at the rate of its own day (app/tax/rates.py).

Money is whole centavos throughout, rounded half up, once per line; the
invoice's totals are the sums of its lines, so they always add up.

For each line:

    price     = quantity × unit price − line discount   (as entered)
    base      = price without the tax it carries, when prices include tax
    relief    = a discount the law gives this buyer, off the base (0 mostly)
    taxable   = base − relief
    tax       = taxable × the rate of the code that applies
    total     = taxable + tax
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Literal, Protocol

Bucket = Literal["taxable", "zero_rated", "exempt", "non_taxable"]
FULL = 10_000  # basis points in 100%


def div_half_up(numerator: int, denominator: int) -> int:
    """numerator / denominator, rounded half up, for numbers that aren't negative."""
    return (2 * numerator + denominator) // (2 * denominator)


@dataclass(frozen=True)
class Code:
    """A tax code: what a line is taxed as, and where it shows on the invoice."""

    code: str
    name: str
    bucket: Bucket
    # Whether it has a rate. Exempt and non-taxable sales carry none.
    rated: bool = True


@dataclass(frozen=True)
class Resolution:
    """What a pack decides for one line."""

    # The code the line would have for a regular buyer: its price carries this
    # tax when prices include tax, so this is what's taken out of it.
    normal: str
    # The code that applies to this buyer.
    applied: str
    # A discount the law gives this buyer, in basis points of the base.
    relief_bp: int = 0
    relief_label: str | None = None


class Pack(Protocol):
    country: str
    name: str
    codes: dict[str, Code]

    def resolve(self, regime: str, treatment: str, category: str, relief_eligible: bool) -> Resolution: ...

    def seller_tax(self, regime: str) -> str | None: ...


RateLookup = Callable[[str, date], int | None]


class TaxError(ValueError):
    """A sale the engine can't tax: a missing rate, an unknown code."""


@dataclass(frozen=True)
class LineIn:
    quantity: int
    unit_price: int
    category: str
    discount: int = 0
    relief_eligible: bool = False
    ref: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class SaleIn:
    regime: str
    treatment: str
    prices_include_tax: bool
    on: date
    lines: list[LineIn]


@dataclass
class LineOut:
    ref: str | None
    description: str | None
    code: str
    code_name: str
    bucket: Bucket
    rate_bp: int
    price: int
    base: int
    relief: int
    taxable: int
    tax: int
    total: int


@dataclass
class SaleOut:
    lines: list[LineOut]
    # What the invoice's summary shows, by bucket.
    taxable_sales: int = 0
    tax: int = 0
    zero_rated_sales: int = 0
    exempt_sales: int = 0
    non_taxable_sales: int = 0
    relief: int = 0
    relief_label: str | None = None
    total_due: int = 0
    # Tax the seller owes on these sales that isn't on the invoice (a non-VAT
    # seller's percentage tax): for their own records, not the buyer's.
    seller_tax: int = 0
    seller_tax_code: str | None = None
    seller_tax_rate_bp: int = 0
    rates_used: dict[str, int] = field(default_factory=dict)


def _rate(rates: RateLookup, pack: Pack, code: str, on: date) -> int:
    known = pack.codes.get(code)
    if known is None:
        raise TaxError(f"{pack.name} has no tax code {code}.")
    if not known.rated:
        return 0
    bp = rates(code, on)
    if bp is None:
        raise TaxError(f"There's no {known.name} rate on record for {on.isoformat()}.")
    return bp


def compute(pack: Pack, rates: RateLookup, sale: SaleIn) -> SaleOut:
    out = SaleOut(lines=[])
    for n, line in enumerate(sale.lines):
        if line.quantity < 1 or line.unit_price < 0 or line.discount < 0:
            raise TaxError(f"Line {n + 1}: quantity, price and discount can't be negative.")
        price = line.quantity * line.unit_price - line.discount
        if price < 0:
            raise TaxError(f"Line {n + 1}: the discount is more than the line.")
        r = pack.resolve(sale.regime, sale.treatment, line.category, line.relief_eligible)
        normal_bp = _rate(rates, pack, r.normal, sale.on)
        applied_bp = _rate(rates, pack, r.applied, sale.on)
        base = div_half_up(price * FULL, FULL + normal_bp) if sale.prices_include_tax else price
        relief = div_half_up(base * r.relief_bp, FULL) if r.relief_bp else 0
        taxable = base - relief
        if sale.prices_include_tax and not relief and applied_bp == normal_bp:
            # A regular line at a tax-inclusive price: the buyer pays exactly
            # the price, so the tax is whatever the base left of it.
            tax = price - base
        else:
            tax = div_half_up(taxable * applied_bp, FULL)
        code = pack.codes[r.applied]
        out.lines.append(
            LineOut(line.ref, line.description, code.code, code.name, code.bucket, applied_bp, price, base, relief, taxable, tax, taxable + tax)
        )
        out.rates_used[code.code] = applied_bp
        if relief:
            out.relief += relief
            out.relief_label = r.relief_label
        if code.bucket == "taxable":
            out.taxable_sales += taxable
            out.tax += tax
        elif code.bucket == "zero_rated":
            out.zero_rated_sales += taxable
        elif code.bucket == "exempt":
            out.exempt_sales += taxable
        else:
            out.non_taxable_sales += taxable
        out.total_due += taxable + tax

    seller_code = pack.seller_tax(sale.regime)
    if seller_code:
        bp = _rate(rates, pack, seller_code, sale.on)
        out.seller_tax_code, out.seller_tax_rate_bp = seller_code, bp
        out.seller_tax = div_half_up(out.total_due * bp, FULL)
    return out
