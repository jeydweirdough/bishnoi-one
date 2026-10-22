"""One search across the CRM (benchmark G2, after Twenty's command menu):
customers, contacts, deals, quotes and products, a few of each, for the
command menu (Ctrl+K). Each kind only when the person may see it, and only
the records their role reaches, the same rules each list keeps.

Each kind says how many match in all (the menu's scope tabs show it), and
each record carries a few facts and next steps for the menu's preview.
"""

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.access import CurrentAccess
from app.deps import DB
from app.models import Company, Contact, Deal, Product, Quote
from app.routers.quotes import reachable
from app.scope import within

router = APIRouter(tags=["search"])

PER_KIND = 5


def fact(label: str, value) -> dict | None:
    """One line of the preview; left out when there's nothing to say."""
    return {"label": label, "value": str(value)} if value not in (None, "") else None


def money(label: str, centavos: int | None) -> dict:
    """An amount in centavos, so the screen formats and shortens it its own way."""
    return {"label": label, "amount": centavos or 0}


def facts(*rows: dict | None) -> list[dict]:
    return [r for r in rows if r]


@router.get("/search")
def search(access: CurrentAccess, db: DB, q: str = Query(..., min_length=1, max_length=100), limit: int = Query(PER_KIND, ge=1, le=20)) -> dict:
    """What matches, by kind, best first (names starting with what was typed, then containing it)."""
    text = q.strip().lower()
    if not text:
        return {"q": q, "groups": []}
    like, starts = f"%{text}%", f"{text}%"
    groups: list[dict] = []

    def ranked(query, name_col):
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.scalars(query.order_by(func.lower(name_col).like(starts).desc(), func.lower(name_col)).limit(limit)).unique().all()
        return rows, total

    def group(kind: str, label: str, found: tuple[list, int], item) -> None:
        rows, total = found
        if rows:
            groups.append({"kind": kind, "label": label, "total": total, "items": [item(r) for r in rows]})

    if access.can("customers.view"):
        group(
            "customers",
            "Customers",
            ranked(
                within(select(Company), Company, access).where(
                    or_(func.lower(Company.name).like(like), func.lower(Company.code).like(like), func.lower(Company.city).like(like), Company.phone.like(like))
                ),
                Company.name,
            ),
            lambda c: {
                "id": c.id,
                "title": c.name,
                "sub": " · ".join(x for x in (c.code, c.city) if x),
                "href": f"/companies/{c.id}",
                "facts": facts(fact("Type", c.industry), fact("City", c.city), fact("Phone", c.phone), fact("Assigned to", c.owner.full_name)),
                "actions": [{"label": "Open customer", "href": f"/companies/{c.id}"}]
                + ([{"label": "New quote", "href": f"/companies/{c.id}/quotes/new"}] if access.can("quotes.create") else [])
                + ([{"label": "New deal", "href": f"/deals/new?company={c.id}"}] if access.can("deals.create") else []),
            },
        )
        group(
            "contacts",
            "Contacts",
            ranked(
                within(select(Contact), Contact, access).where(
                    or_(
                        func.lower(Contact.first_name + " " + func.coalesce(Contact.last_name, "")).like(like),
                        func.lower(func.coalesce(Contact.email, "")).like(like),
                        func.coalesce(Contact.mobile, "").like(like),
                        func.coalesce(Contact.phone, "").like(like),
                    )
                ),
                Contact.first_name,
            ),
            lambda c: {
                "id": c.id,
                "title": c.full_name,
                "sub": " · ".join(x for x in (c.job_title, c.company.name if c.company else None) if x),
                "href": f"/contacts/{c.id}",
                "facts": facts(fact("Job title", c.job_title), fact("Customer", c.company.name if c.company else None), fact("Email", c.email), fact("Mobile", c.mobile or c.phone)),
                "actions": [{"label": "Open contact", "href": f"/contacts/{c.id}"}]
                + ([{"label": "Open customer", "href": f"/companies/{c.company_id}"}] if c.company_id else []),
            },
        )
    if access.can("deals.view"):
        group(
            "deals",
            "Deals",
            ranked(within(select(Deal), Deal, access).where(func.lower(Deal.name).like(like)), Deal.name),
            lambda d: {
                "id": d.id,
                "title": d.name,
                "sub": d.company.name,
                "href": f"/deals/{d.id}",
                "facts": facts(fact("Customer", d.company.name), fact("Stage", d.stage.name), money("Value", d.value_centavos), fact("Expected close", d.expected_close_on)),
                "actions": [{"label": "Open deal", "href": f"/deals/{d.id}"}, {"label": "Open customer", "href": f"/companies/{d.company_id}"}],
            },
        )
    if access.can("quotes.view"):
        group(
            "quotes",
            "Quotes",
            ranked(
                reachable(select(Quote), access).where(or_(func.lower(Quote.number).like(like), func.lower(Quote.customer_name).like(like))),
                Quote.number,
            ),
            lambda x: {
                "id": x.id,
                "title": x.number,
                "sub": x.customer_name,
                "href": f"/quotes/{x.id}",
                "facts": facts(fact("Customer", x.customer_name), fact("Price type", x.price_type_name), money("Total", x.total_centavos), fact("Valid until", x.valid_until)),
                "actions": [{"label": "Open quote", "href": f"/quotes/{x.id}"}]
                + ([{"label": "Open customer", "href": f"/companies/{x.company_id}"}] if x.company_id else []),
            },
        )
    if access.can("products.view"):
        group(
            "products",
            "Products",
            ranked(
                select(Product).where(Product.is_active, or_(func.lower(Product.name).like(like), func.lower(Product.code).like(like), func.lower(func.coalesce(Product.generic_name, "")).like(like))),
                Product.name,
            ),
            lambda p: {
                "id": p.id,
                "title": p.name,
                "sub": " · ".join(x for x in (p.code, p.generic_name, p.strength) if x),
                "href": f"/products?q={p.code or p.name}",
                "facts": facts(fact("Code", p.code), fact("Generic name", p.generic_name), fact("Strength", p.strength), fact("Form", p.form), fact("Prescription", "Needed" if p.needs_prescription else None)),
                "actions": [{"label": "Open product", "href": f"/products?q={p.code or p.name}"}],
            },
        )
    return {"q": q, "groups": groups}
