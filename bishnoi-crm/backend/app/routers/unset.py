"""What isn't set up yet, for the sidebar's red counts.

Each count is a thing somebody has to fill in before the CRM works in full: a
product with no price can't be quoted at that price type, a quote can't be
printed with no quotation form. Only the counts this person may fix are sent,
so a mark in their sidebar is always one they can act on.
"""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.access import CurrentAccess
from app.deps import DB
from app.models import Product, QuoteTemplate
from app.pricing import sales_settings
from app.routers.catalogue import missing_a_price

router = APIRouter(tags=["unset"])


@router.get("/unset")
def unset(access: CurrentAccess, db: DB) -> dict[str, int]:
    """How many of each thing isn't set yet, by kind. Kinds are left out when
    this person can't fix them, and when nothing is missing."""
    counts: dict[str, int] = {}
    if access.can("products.edit"):
        counts["productPrices"] = db.scalar(select(func.count()).select_from(Product).where(missing_a_price())) or 0
    if access.can("admin.settings"):
        # Printing picks an active form, or an uploaded Excel form that has its file.
        usable = select(QuoteTemplate.id).where(QuoteTemplate.is_active, (QuoteTemplate.kind == "form") | QuoteTemplate.excel_ref.is_not(None)).exists()
        counts["quoteTemplates"] = 0 if db.scalar(select(usable)) else 1
        # The letterhead printed on every quote.
        rules = sales_settings(db)
        counts["companyDetails"] = sum(1 for v in (rules.company_address, rules.company_tin, rules.company_contact) if not (v or "").strip())
    return {k: v for k, v in counts.items() if v}
