"""Money, written the way a company writes it.

Amounts are whole minor units everywhere — centavos for a peso company, cents
for a dollar one — so nothing here ever sees a float. How many minor units make
a unit, and what the money is called, belong to the company (`organizations`),
not to Orbit.

The web app formats money properly with Intl, which knows every currency and
every locale. This is only for the few sentences the API writes itself, so it
keeps a short list of symbols and falls back to the ISO code, which is always
correct if not always pretty.
"""

from sqlalchemy.orm import Session

from app.models import Organization
from app.tenancy import company_of

SYMBOLS = {
    "PHP": "₱", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "AUD": "A$", "CAD": "C$", "SGD": "S$", "HKD": "HK$", "MYR": "RM", "THB": "฿",
    "IDR": "Rp", "VND": "₫", "INR": "₹", "CNY": "¥", "KRW": "₩",
}


def format_money(minor: int, currency: str = "PHP", minor_units: int = 2) -> str:
    """1250000 -> "₱12,500.00". A currency with no minor units (yen) gets none."""
    symbol = SYMBOLS.get(currency.upper())
    whole = minor / (10**minor_units) if minor_units else minor
    amount = f"{whole:,.{minor_units}f}"
    return f"{symbol}{amount}" if symbol else f"{currency.upper()} {amount}"


def money(db: Session, minor: int) -> str:
    """The amount, in the session's company's own money."""
    org = db.get(Organization, company_of(db))
    if org is None:
        return format_money(minor)
    return format_money(minor, org.currency, org.minor_units)


def money_name(db: Session) -> str:
    """The symbol alone, for a sentence that names the money without an amount."""
    org = db.get(Organization, company_of(db))
    currency = org.currency if org else "PHP"
    return SYMBOLS.get(currency.upper(), currency.upper())
