"""One search across the CRM (benchmark G2, after Twenty's command menu):
customers, contacts, deals, quotes and products, a few of each, for the
command menu (Ctrl+K). Each kind only when the person may see it, and only
the records their role reaches, the same rules each list keeps.
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


@router.get("/search")
def search(access: CurrentAccess, db: DB, q: str = Query(..., min_length=1, max_length=100), limit: int = Query(PER_KIND, ge=1, le=20)) -> dict:
    """What matches, by kind, best first (names starting with what was typed, then containing it)."""
    text = q.strip().lower()
    if not text:
        return {"q": q, "groups": []}
    like, starts = f"%{text}%", f"{text}%"
    groups: list[dict] = []

    def ranked(query, name_col):
        return db.scalars(query.order_by(func.lower(name_col).like(starts).desc(), func.lower(name_col)).limit(limit)).unique().all()

    if access.can("customers.view"):
        companies = ranked(
            within(select(Company), Company, access).where(
                or_(func.lower(Company.name).like(like), func.lower(Company.code).like(like), func.lower(Company.city).like(like), Company.phone.like(like))
            ),
            Company.name,
        )
        if companies:
            groups.append({"kind": "customers", "label": "Customers", "items": [
                {"id": c.id, "title": c.name, "sub": " · ".join(x for x in (c.code, c.city) if x), "href": f"/companies/{c.id}"} for c in companies
            ]})
        contacts = ranked(
            within(select(Contact), Contact, access).where(
                or_(
                    func.lower(Contact.first_name + " " + func.coalesce(Contact.last_name, "")).like(like),
                    func.lower(func.coalesce(Contact.email, "")).like(like),
                    func.coalesce(Contact.mobile, "").like(like),
                    func.coalesce(Contact.phone, "").like(like),
                )
            ),
            Contact.first_name,
        )
        if contacts:
            groups.append({"kind": "contacts", "label": "Contacts", "items": [
                {"id": c.id, "title": c.full_name, "sub": " · ".join(x for x in (c.job_title, c.company.name if c.company else None) if x), "href": f"/contacts/{c.id}"}
                for c in contacts
            ]})
    if access.can("deals.view"):
        deals = ranked(within(select(Deal), Deal, access).where(func.lower(Deal.name).like(like)), Deal.name)
        if deals:
            groups.append({"kind": "deals", "label": "Deals", "items": [
                {"id": d.id, "title": d.name, "sub": d.company.name, "href": f"/deals/{d.id}"} for d in deals
            ]})
    if access.can("quotes.view"):
        quotes = ranked(
            reachable(select(Quote), access).where(or_(func.lower(Quote.number).like(like), func.lower(Quote.customer_name).like(like))),
            Quote.number,
        )
        if quotes:
            groups.append({"kind": "quotes", "label": "Quotes", "items": [
                {"id": x.id, "title": x.number, "sub": x.customer_name, "href": f"/quotes/{x.id}"} for x in quotes
            ]})
    if access.can("products.view"):
        products = ranked(
            select(Product).where(Product.is_active, or_(func.lower(Product.name).like(like), func.lower(Product.code).like(like), func.lower(func.coalesce(Product.generic_name, "")).like(like))),
            Product.name,
        )
        if products:
            groups.append({"kind": "products", "label": "Products", "items": [
                {"id": p.id, "title": p.name, "sub": " · ".join(x for x in (p.code, p.generic_name, p.strength) if x), "href": f"/products?q={p.code or p.name}"} for p in products
            ]})
    return {"q": q, "groups": groups}
