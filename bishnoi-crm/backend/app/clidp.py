"""CLIDP: the FDA's Certificate of Listing of Identical Drug Product, per product.

The certificate is a regulatory document (its home is the Regulatory app);
the CRM keeps each product's CLIDP number and how long it's valid, on the
product form (app/tools/division_forms.py adds the two fields), and warns
before a quote or a bid goes out with a product whose CLIDP:
- has run out, for any customer; or
- isn't on file, for the divisions that need one to sell (B2B and BID).
A warning, never a block: the certificate may be on its way.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Product

NUMBER = "x_clidp_number"
VALID_UNTIL = "x_clidp_valid_until"
# The teams (divisions) that need a product's CLIDP on file to sell it.
NEEDED_BY = ("B2B", "BID")


def warnings(db: Session, product_codes: list[str], company: Company | None, today: str) -> list[str]:
    """What to say about the CLIDPs of these products, for this customer, as of `today` (YYYY-MM-DD)."""
    codes = list(dict.fromkeys(c for c in product_codes if c))
    if not codes:
        return []
    needed = bool(company and company.team and company.team.name.upper() in NEEDED_BY)
    out = []
    for p in db.scalars(select(Product).where(Product.code.in_(codes)).order_by(Product.name)):
        extra = p.extra or {}
        until = str(extra.get(VALID_UNTIL) or "")
        if until and until < today:
            out.append(f"{p.name}: its CLIDP ran out on {until}.")
        elif needed and not extra.get(NUMBER):
            out.append(f"{p.name}: no CLIDP on file.")
    return out
