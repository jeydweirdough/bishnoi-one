"""Order links: medicine search and a quote, for the customer.

A rep makes a link for a customer and says how long it lives (an hour, a day,
a few days). The customer opens it, with no account: they search the
medicines, at the prices of that customer and price type only, pick the
quantities, and send. A quote is made for them, the rep's, by the same step as
any quote (approval when a price needs one, the numbering, the audit log), and
it prints as the quotation letter.

A link can be for a customer, or for someone who isn't one yet (made from
Customers → Order links): they say who they are when they order, and become
the rep's customer, in the rep's division (or the rep's customer with the same
email or mobile, if there is one), with the quote theirs.

A link works once, and stops when it expires or the rep switches it off: to
order again, the customer asks for a new one. Only its hash is kept, so a link
can't be read back from the database, and an old one can't be used again.
Nothing about other customers, other price types or the rep's own figures is
ever shown through it.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import Field
from sqlalchemy import select

from app.access import Access, CurrentAccess
from app.api import Api, digits, iso, not_found
from app.audit import audit
from app.connections import NoKey, seal, unseal
from app.deps import DB, CurrentUser, SettingsDep, as_utc
from app.extra import check_extra
from app.models import Company, Contact, QuoteLink, User
from app.pricing import price_book, price_lines, today
from app.routers.customer_types import first_type
from app.routers.quotes import Discount, LineIn, QuoteIn, book_for, save_quote, with_tax
from app.scope import reaches
from app.security import new_token, token_hash
from app.tenants import company_of

router = APIRouter(tags=["quotes"])

# How long a link may live: an hour, up to a week.
LIFETIMES = (1, 4, 24, 72, 168)
def money(centavos: int) -> str:
    return f"\u20b1{centavos / 100:,.2f}"


GONE = "This link has expired or was already used. Ask your medical representative for a new one."


def link_state(link: QuoteLink, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if link.revoked_at:
        return "switched_off"
    if link.used_at:
        return "used"
    if as_utc(link.expires_at) <= now:
        return "expired"
    return "open"


def link_out(link: QuoteLink) -> dict:
    return {
        "id": link.id,
        "state": link_state(link),
        "priceType": link.price_type,
        "createdAt": iso(link.created_at),
        "expiresAt": iso(link.expires_at),
        "usedAt": iso(link.used_at),
        "quoteId": link.quote_id,
        "customer": {"id": link.company.id, "name": link.company.name} if link.company else None,
        "owner": {"id": link.owner.id, "name": link.owner.full_name},
    }


def book_of(db, link_or_company, rep: User | None, on: str):
    """The prices a link shows: its customer's, or, for someone not a customer yet, the rep's division's."""
    company = link_or_company.company if isinstance(link_or_company, QuoteLink) else link_or_company
    contact = link_or_company.contact if isinstance(link_or_company, QuoteLink) else None
    if company is not None:
        return book_for(db, company, contact, on)
    return price_book(db, rep.team_id if rep else None, on, None)


def listed_types(book) -> list:
    """Price types a customer can see on a link: list prices, never ones a rep types in or must explain."""
    return [t for t in book.price_types if t.entry == "list" and not t.requires_notes]


# --- for staff: making, seeing and switching off a customer's links ---------------------------


class LinkIn(Api):
    hours: int = Field(24, ge=1, le=168)
    price_type: str | None = Field(None, max_length=40)
    contact_id: str | None = Field(None, max_length=36)


def reachable_company(db, access: Access, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None or not reaches(company, access):
        raise not_found("customer")
    return company


def links_answer(db, links, book) -> dict:
    return {
        "items": [link_out(l) for l in links],
        "priceTypes": [{"code": t.code, "name": t.name} for t in listed_types(book)],
        "lifetimes": list(LIFETIMES),
    }


@router.get("/companies/{company_id}/quote-links")
def list_links(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, company_id: str) -> dict:
    access.require("quotes.view")
    company = reachable_company(db, access, company_id)
    links = db.scalars(select(QuoteLink).where(QuoteLink.company_id == company.id).order_by(QuoteLink.created_at.desc()).limit(10)).unique()
    return links_answer(db, links, book_of(db, company, me, today(settings.org_timezone)))


@router.get("/quote-links")
def my_links(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    """The links this person made: for customers, and for people not customers yet (Customers → Order links)."""
    access.require("quotes.view")
    links = db.scalars(select(QuoteLink).where(QuoteLink.owner_id == me.id).order_by(QuoteLink.created_at.desc()).limit(50)).unique()
    return links_answer(db, links, book_of(db, None, me, today(settings.org_timezone)))


def make_link(db, me: User, settings, company: Company | None, body: "LinkIn") -> dict:
    """A new link: its address is in the answer, to copy and send; its maker can copy it again while it works."""
    book = book_of(db, company, me, today(settings.org_timezone))
    types = listed_types(book)
    if not types:
        raise HTTPException(status.HTTP_409_CONFLICT, "There are no list prices to show. Set up the price list first (Settings → Pricing).")
    kind = next((t for t in types if t.code == body.price_type), None) if body.price_type else next((t for t in types if not t.needs_approval), types[0])
    if kind is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "priceType"], "msg": "Pick one of the list prices."}])
    contact = None
    if body.contact_id:
        contact = db.get(Contact, body.contact_id)
        if contact is None or company is None or contact.company_id != company.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "contactId"], "msg": "Pick one of this customer's contacts."}])
    token = new_token()
    try:
        sealed = seal(settings, {"token": token})
    except NoKey:
        sealed = None  # online and not connected to the platform: it works, but can't be copied again
    link = QuoteLink(
        token_hash=token_hash(token),
        token_sealed=sealed,
        company_id=company.id if company else None,
        contact_id=contact.id if contact else None,
        price_type=kind.code,
        owner_id=me.id,
        expires_at=datetime.now(UTC) + timedelta(hours=body.hours),
    )
    db.add(link)
    db.flush()
    audit(db, me, "quote_link.created", target=company.name if company else "A new customer", target_type="company" if company else None, target_id=company.id if company else None)
    db.commit()
    db.refresh(link)
    return {**link_out(link), "token": token}


@router.post("/companies/{company_id}/quote-links", status_code=status.HTTP_201_CREATED)
def create_link(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, company_id: str, body: LinkIn) -> dict:
    access.require("quotes.create")
    return make_link(db, me, settings, reachable_company(db, access, company_id), body)


@router.post("/quote-links", status_code=status.HTTP_201_CREATED)
def create_open_link(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, body: LinkIn) -> dict:
    """A link for someone not a customer yet: they become the rep's customer when they order."""
    access.require("quotes.create")
    access.require("customers.create")
    return make_link(db, me, settings, None, body)


def own_link(db, access: Access, me: User, link_id: str) -> QuoteLink:
    """A link this person may change: their own, or one on a customer they reach."""
    access.require("quotes.create")
    link = db.get(QuoteLink, link_id)
    if link is None or not (link.owner_id == me.id or (link.company is not None and reaches(link.company, access))):
        raise not_found("link")
    return link


@router.get("/quote-links/{link_id}/token")
def link_token(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, link_id: str) -> dict:
    """The link again, to copy and send, while it hasn't been used."""
    link = own_link(db, access, me, link_id)
    if link.used_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "This link was used: it made its quote. Make a new link for the next order.")
    token = unseal(settings, link.token_sealed).get("token")
    if not token:
        raise HTTPException(status.HTTP_409_CONFLICT, "This link can't be copied again: it was made before links were kept. Delete it and make a new one.")
    return {"token": token}


def link_name(link: QuoteLink) -> str:
    return link.company.name if link.company else "A new customer"


class LinkPatch(Api):
    """What a link's maker changes: how long from now it works, its price, and whether it's on."""

    hours: int | None = Field(None, ge=1, le=168)
    price_type: str | None = Field(None, max_length=40)
    on: bool | None = None


@router.patch("/quote-links/{link_id}")
def change_link(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, link_id: str, body: LinkPatch) -> dict:
    """Changed while it hasn't been used: a used link made its quote, and stays as it was."""
    link = own_link(db, access, me, link_id)
    if link.used_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "This link was used: it made its quote. Make a new link for the next order.")
    now = datetime.now(UTC)
    if body.price_type is not None:
        book = book_of(db, link, link.owner, today(settings.org_timezone))
        if body.price_type not in {t.code for t in listed_types(book)}:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "priceType"], "msg": "Pick one of the list prices."}])
        link.price_type = body.price_type
    if body.hours is not None:
        link.expires_at = now + timedelta(hours=body.hours)  # from now: a lapsed link can be given more time
    if body.on is not None:
        link.revoked_at = None if body.on else (link.revoked_at or now)
    audit(db, me, "quote_link.changed", target=link_name(link), target_type="company" if link.company else None, target_id=link.company_id)
    db.commit()
    db.refresh(link)
    return link_out(link)


@router.delete("/quote-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(access: CurrentAccess, me: CurrentUser, db: DB, link_id: str) -> None:
    """Gone from the list, and it can't be opened. A quote it already made stays, on its customer."""
    link = own_link(db, access, me, link_id)
    audit(db, me, "quote_link.deleted", target=link_name(link), target_type="company" if link.company else None, target_id=link.company_id)
    db.delete(link)
    db.commit()


# --- for the customer: the link itself, with no account ----------------------------------------


def open_link(db, token: str) -> QuoteLink:
    link = db.scalar(select(QuoteLink).where(QuoteLink.token_hash == token_hash(token)))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, GONE)
    if link_state(link) != "open":
        raise HTTPException(status.HTTP_410_GONE, GONE)
    return link


@router.get("/public/quote-links/{token}")
def read_link(request: Request, db: DB, settings: SettingsDep, token: str) -> dict:
    """What the customer sees: who it's for, until when, and the medicines at their price."""
    link = open_link(db, token[:100])
    book = book_of(db, link, link.owner, today(settings.org_timezone))
    kind = book.price_type(link.price_type)
    products = []
    for p in book.products.values():
        price = book.prices.get(p.id, {}).get(link.price_type)
        if not price:
            continue
        products.append({"id": p.id, "code": p.code, "name": p.name, "genericName": p.generic_name, "strength": p.strength, "form": p.form, "unit": p.unit, "priceCentavos": price})
    products.sort(key=lambda x: x["name"].lower())
    return {
        "company": company_of(request),
        "orgName": settings.org_name,
        "customer": link.company.name if link.company else None,
        "contact": link.contact.full_name if link.contact else None,
        # Not a customer yet: the page asks who they are before they send.
        "asksWho": link.company is None,
        "rep": link.owner.full_name,
        "priceType": kind.name if kind else link.price_type,
        "expiresAt": iso(link.expires_at),
        "products": products,
    }


class OrderLine(Api):
    product_id: str = Field(max_length=36)
    quantity: int = Field(ge=1, le=100_000)
    # The price per unit the customer asks for instead of the link's: the quote waits for approval.
    asked_price_centavos: int | None = Field(None, ge=1)


class NewCustomer(Api):
    """Who's ordering, on a link for someone not a customer yet."""

    name: str = Field(min_length=2, max_length=160)
    contact_name: str | None = Field(None, max_length=160)
    mobile: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=254)
    city: str | None = Field(None, max_length=80)


class OrderIn(Api):
    lines: list[OrderLine] = Field(min_length=1, max_length=50)
    note: str | None = Field(None, max_length=1000)
    customer: NewCustomer | None = None


def customer_from(db, rep: User, who: NewCustomer) -> tuple[Company, Contact | None]:
    """The rep's customer this order is for: theirs already, by the same email or
    mobile; else a new one, the rep's, in the rep's division, with a contact."""
    email = (who.email or "").strip().lower() or None
    mobile = digits(who.mobile)
    for c in db.scalars(select(Company).where(Company.owner_id == rep.id)).unique():
        if (email and (c.email or "").lower() == email) or (mobile and len(mobile) >= 7 and digits(c.phone) == mobile):
            return c, None
    company = Company(
        name=who.name.strip(),
        status=first_type(db, team_id=rep.team_id),
        email=email,
        phone=(who.mobile or "").strip() or None,
        city=(who.city or "").strip() or None,
        notes="Added from an order link, when they ordered.",
        owner_id=rep.id,
        team_id=rep.team_id,
        created_by_id=rep.id,
    )
    db.add(company)
    db.flush()
    contact = None
    if who.contact_name and who.contact_name.strip():
        first, _, last = who.contact_name.strip().partition(" ")
        contact = Contact(company_id=company.id, first_name=first[:80], last_name=last[:80] or None, email=email, mobile=(who.mobile or "").strip() or None, owner_id=rep.id, team_id=rep.team_id, created_by_id=rep.id)
        db.add(contact)
        db.flush()
    audit(db, rep, "company.created", target=company.name, target_type="company", target_id=company.id)
    return company, contact


@router.post("/public/quote-links/{token}", status_code=status.HTTP_201_CREATED)
def place_order(db: DB, settings: SettingsDep, token: str, body: OrderIn) -> dict:
    """The customer's picks, made into a quote for them, the rep's. The link is used up."""
    link = open_link(db, token[:100])
    company, contact, rep = link.company, link.contact, db.get(User, link.owner_id)
    if rep is None or not rep.is_active:
        raise HTTPException(status.HTTP_410_GONE, GONE)
    if company is None and body.customer is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "customer", "name"], "msg": "Say who's ordering: your name, or your business's."}])
    if company is None and not ((body.customer.mobile or "").strip() or (body.customer.email or "").strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "customer", "mobile"], "msg": "Give a mobile number or an email, so your rep can reach you."}])
    book = book_of(db, link, rep, today(settings.org_timezone))
    kind = book.price_type(link.price_type)
    if kind is None:
        raise HTTPException(status.HTTP_410_GONE, GONE)
    seen: dict[str, int] = {}
    asked: dict[str, int] = {}
    for line in body.lines:  # the same medicine twice is one line
        seen[line.product_id] = seen.get(line.product_id, 0) + line.quantity
        if line.asked_price_centavos:
            asked[line.product_id] = line.asked_price_centavos
    allowed = {pid for pid in book.products if book.prices.get(pid, {}).get(link.price_type)}
    if any(pid not in allowed for pid in seen):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "One of the medicines isn't offered on this link. Reload the page and pick again.")
    # An asked price: lower than the link's, it's the line's discount (what's asked off each unit, times how many).
    listed = {pid: book.prices[pid][link.price_type] for pid in seen}
    asked = {pid: price for pid, price in asked.items() if price < listed[pid]}
    words = [f"{book.products[pid].name}: asked {money(price)} a unit (the price was {money(listed[pid])})" for pid, price in asked.items()]
    note = " ".join(x for x in ("Ordered by the customer through a link.", (body.note or "").strip(), ("The customer asked for another price. " + "; ".join(words) + ".") if words else "") if x)

    def lines(with_asked: bool) -> list[LineIn]:
        return [
            LineIn(product_id=pid, quantity=qty, discount=Discount(kind="amount", value=(listed[pid] - asked[pid]) * qty) if with_asked and pid in asked else None)
            for pid, qty in seen.items()
        ]

    quote = QuoteIn(price_type=kind.code, notes=note[:2000], lines=lines(True))
    try:
        priced = price_lines(book, quote.price_type, quote.rx, [l.model_dump(by_alias=True) for l in quote.lines])
    except HTTPException:
        if not asked:
            raise
        # Discounts are off in the price rules: the asked prices stay in the notes, for the approver.
        quote = QuoteIn(price_type=kind.code, notes=note[:2000], lines=lines(False))
        priced = price_lines(book, quote.price_type, quote.rx, [l.model_dump(by_alias=True) for l in quote.lines])
    priced = with_tax(settings, book, priced)
    if asked:
        # Asked for: someone decides, however small the change.
        priced["approvalReasons"] = sorted({*priced["approvalReasons"], "asked"})
    if company is None:
        # Now they're a customer: the rep's, priced as above.
        company, contact = customer_from(db, rep, body.customer)
        link.company_id, link.contact_id = company.id, contact.id if contact else None
    record = save_quote(db, settings, rep, company, contact, quote, priced, kind, None, None, check_extra(db, "quote", None), book.settings)
    link.used_at = datetime.now(UTC)
    link.quote_id = record.id
    db.commit()
    return {
        "number": record.number,
        "totalCentavos": record.total_centavos,
        "lines": [{"name": l.get("productName"), "quantity": l.get("quantity"), "totalCentavos": l.get("totalCentavos")} for l in record.lines],
        "waitsForApproval": record.approval_status == "pending",
        "rep": rep.full_name,
    }
