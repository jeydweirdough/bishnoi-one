"""The Philippines: VAT, and what a Sales Invoice has to show.

**Confirm with your accountant before relying on it for filing.** It is what
the law is understood to say as of 2026, written down so the engine can apply
it; it isn't tax advice.

- VAT is 12% (National Internal Revenue Code sec. 106 and 108; 12% since
  1 February 2006, RA 9337). Zero-rated sales (sec. 106(A)(2), 108(B), e.g.
  export sales and sales to registered export enterprises) are taxed at 0%.
  VAT-exempt sales (sec. 109, e.g. medicines on the FDA's exempt lists) carry
  no VAT. Which products are zero-rated or exempt is set per product: the
  pack doesn't keep the lists, which change.
- A seller that isn't VAT-registered puts no VAT on its invoices and pays
  percentage tax on its gross sales (sec. 116): 3%, except 1% from 1 July 2020
  to 30 June 2023 (RA 11534, CREATE).
- Senior citizens (RA 9994) and persons with disability (RA 10754) buying
  medicines and other covered goods for their own use get a 20% discount and
  VAT exemption. For a VAT-registered seller the 20% comes off the price
  without VAT, and the sale is VAT-exempt (RR 7-2010): ₱112.00 with VAT is
  ₱100.00 without it, less ₱20.00, so ₱80.00 is due. Their name and ID number
  go on the invoice. (The 5% discount on basic necessities is not covered
  here.)
- Since the Ease of Paying Taxes Act (RA 11976, 2024) the Sales Invoice is the
  primary document. It shows the seller's registered name, TIN and branch
  code and address, and, for a VAT-registered seller, VATable sales, VAT,
  zero-rated sales and VAT-exempt sales separately.
"""

from dataclasses import dataclass
from app.tax.engine import Code, Resolution

country = "PH"
name = "Philippines"
currency = "PHP"

VAT = "PH_VAT12"
ZERO = "PH_ZERO"
EXEMPT = "PH_EXEMPT"
NON_VAT = "PH_NONVAT"
PERCENTAGE = "PH_PT"

codes: dict[str, Code] = {
    VAT: Code(VAT, "VAT 12%", "taxable"),
    ZERO: Code(ZERO, "Zero-rated", "zero_rated"),
    EXEMPT: Code(EXEMPT, "VAT-exempt", "exempt", rated=False),
    NON_VAT: Code(NON_VAT, "Non-VAT sale", "non_taxable", rated=False),
    # The seller's own tax when it isn't VAT-registered: not on the invoice.
    PERCENTAGE: Code(PERCENTAGE, "Percentage tax (non-VAT seller)", "non_taxable"),
}

# code, rate in basis points, valid from, valid to (None: still in force), where it comes from
RATES: tuple[tuple[str, int, str, str | None, str], ...] = (
    (VAT, 1200, "2006-02-01", None, "NIRC sec. 106/108, as amended by RA 9337"),
    (ZERO, 0, "2006-02-01", None, "NIRC sec. 106(A)(2), 108(B)"),
    (PERCENTAGE, 300, "2018-01-01", "2020-06-30", "NIRC sec. 116, as amended by RA 10963 (TRAIN)"),
    (PERCENTAGE, 100, "2020-07-01", "2023-06-30", "NIRC sec. 116, as amended by RA 11534 (CREATE)"),
    (PERCENTAGE, 300, "2023-07-01", None, "NIRC sec. 116"),
)

# What a product can be, for VAT. Set per product.
categories: dict[str, str] = {
    "standard": "VATable (12%)",
    "zero_rated": "Zero-rated (0%)",
    "exempt": "VAT-exempt",
}

# Who is buying. `needs_id`: the invoice has to carry their ID number.
treatments: dict[str, dict] = {
    "regular": {"name": "Regular buyer", "needs_id": False},
    "senior_citizen": {"name": "Senior citizen (RA 9994)", "needs_id": True},
    "pwd": {"name": "Person with disability (RA 10754)", "needs_id": True},
    "zero_rated_buyer": {"name": "Zero-rated buyer (export, registered export enterprise)", "needs_id": False},
}

regimes: dict[str, str] = {
    "vat": "VAT-registered",
    "non_vat": "Not VAT-registered (pays percentage tax)",
}

SC_PWD_DISCOUNT_BP = 2000


def resolve(regime: str, treatment: str, category: str, relief_eligible: bool) -> Resolution:
    if regime not in regimes:
        raise ValueError(f"Unknown regime {regime!r}.")
    if treatment not in treatments:
        raise ValueError(f"Unknown buyer {treatment!r}.")
    if category not in categories:
        raise ValueError(f"Unknown VAT category {category!r}.")
    relief = treatment in ("senior_citizen", "pwd") and relief_eligible
    label = f"{treatments[treatment]['name'].split(' (')[0]} discount (20%)" if relief else None
    if regime == "non_vat":
        # No VAT anywhere on a non-VAT seller's invoice; the 20% comes off the price.
        return Resolution(NON_VAT, NON_VAT, SC_PWD_DISCOUNT_BP if relief else 0, label)
    normal = {"standard": VAT, "zero_rated": ZERO, "exempt": EXEMPT}[category]
    if relief:
        # VAT comes off, then 20% off what's left, and the sale is VAT-exempt.
        return Resolution(normal, EXEMPT, SC_PWD_DISCOUNT_BP, label)
    if treatment == "zero_rated_buyer" and category == "standard":
        return Resolution(normal, ZERO)
    return Resolution(normal, normal)


def seller_tax(regime: str) -> str | None:
    return PERCENTAGE if regime == "non_vat" else None


# What the invoice calls things, in the order its summary shows them.
invoice = {
    "document": "Sales Invoice",
    "summary": {
        "vat": [
            ("taxable_sales", "VATable Sales"),
            ("tax", "VAT (12%)"),
            ("zero_rated_sales", "Zero-Rated Sales"),
            ("exempt_sales", "VAT-Exempt Sales"),
        ],
        "non_vat": [("non_taxable_sales", "Total Sales")],
    },
    # Printed on a non-VAT seller's invoices.
    "non_vat_notice": "THIS DOCUMENT IS NOT VALID FOR CLAIM OF INPUT TAX.",
}


# Expanded withholding tax: what a buyer withholds from what it pays a supplier,
# by the BIR's alphanumeric tax code (ATC), with its usual rate (RR 2-98 as
# amended by RR 11-2018). WI: the payee is an individual; WC: a corporation.
# The rate can be changed on a bill: check the BIR's current ATC list for others.
@dataclass(frozen=True)
class Atc:
    code: str
    nature: str
    rate_bp: int


EWT_ATCS: dict[str, Atc] = {a.code: a for a in (
    Atc("WI010", "Professional fees, individual, gross income up to 3 million", 500),
    Atc("WI011", "Professional fees, individual, gross income over 3 million", 1000),
    Atc("WC010", "Professional fees, corporation, gross income up to 720,000", 1000),
    Atc("WC011", "Professional fees, corporation, gross income over 720,000", 1500),
    Atc("WI100", "Rentals of real or personal property, individual", 500),
    Atc("WC100", "Rentals of real or personal property, corporation", 500),
    Atc("WI120", "Income payments to contractors, individual", 200),
    Atc("WC120", "Income payments to contractors, corporation", 200),
    Atc("WI158", "Purchases of goods by top withholding agents, individual supplier", 100),
    Atc("WC158", "Purchases of goods by top withholding agents, corporate supplier", 100),
    Atc("WI160", "Purchases of services by top withholding agents, individual supplier", 200),
    Atc("WC160", "Purchases of services by top withholding agents, corporate supplier", 200),
)}
