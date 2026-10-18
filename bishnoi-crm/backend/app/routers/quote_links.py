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

import secrets
from datetime import UTC, datetime, timedelta
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import Field, ValidationError, field_validator
from sqlalchemy import select

from app.access import Access, CurrentAccess
from app.api import Api, digits, field_error, iso, not_found
from app.audit import audit
from app.connections import NoKey, seal, unseal
from app.deps import DB, CurrentUser, SettingsDep, as_utc
from app.extra import check_extra
from app.models import Company, Contact, QuoteLink, StoredFile, User
from app.pricing import price_book, price_lines, today
from app.routers.customer_types import first_type
from app import storage
from app.routers.quotes import LetterIn, LineIn, QuoteIn, book_for, save_quote, with_tax
from app.scope import reaches
from app.security import new_token, token_hash
from app.tenants import company_of

router = APIRouter(tags=["quotes"])

# How long a link may live: an hour, up to a week.
LIFETIMES = (1, 4, 24, 72, 168)


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
        "asks": asks_out(link),
    }


def asks_out(link: QuoteLink) -> dict:
    """What the customer must send with the order: set by the rep making the link."""
    asks = link.asks or {}
    return {
        "prescriptionAlways": asks.get("prescription") == "always",
        "payer": {"code": asks["payer"], "name": asks.get("payerName") or asks["payer"]} if asks.get("payer") else None,
        "documents": list(asks.get("documents") or []),
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


class LinkAsks(Api):
    """What the customer must send with the order. A prescription is always asked
    for Rx medicines; `prescription_always` asks for one with any order."""

    prescription_always: bool = False
    # Who pays, with a guarantee letter (DSWD, PCSO...): the customer attaches it.
    payer: str | None = Field(None, max_length=40)
    # Named documents to attach, each its own upload: "Valid ID", "Senior citizen card".
    documents: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("documents")
    @classmethod
    def _labels(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for label in value:
            label = " ".join(label.split())[:60]
            if label and label.lower() not in {x.lower() for x in seen}:
                seen.append(label)
        return seen


class LinkIn(Api):
    hours: int = Field(24, ge=1, le=168)
    price_type: str | None = Field(None, max_length=40)
    contact_id: str | None = Field(None, max_length=36)
    asks: LinkAsks | None = None


def asks_from(book, body: LinkAsks | None) -> dict:
    """The asks, as kept: a payer only if the company takes guarantee letters, from its list."""
    body = body or LinkAsks()
    issuer = None
    if body.payer:
        issuer = next((i for i in book.issuers if i.code == body.payer), None) if book.settings.allows_guarantee_letters else None
        if issuer is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "asks", "payer"], "msg": "Pick who pays from the list."}])
    return {"prescription": "always" if body.prescription_always else "rx", "payer": issuer.code if issuer else None, "payerName": issuer.name if issuer else None, "documents": body.documents}


def reachable_company(db, access: Access, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None or not reaches(company, access):
        raise not_found("customer")
    return company


def links_answer(db, links, book) -> dict:
    return {
        "items": [link_out(l) for l in links],
        "priceTypes": [{"code": t.code, "name": t.name} for t in listed_types(book)],
        # Who may pay with a guarantee letter, for a link to ask for one.
        "payers": [{"code": i.code, "name": i.name} for i in book.issuers] if book.settings.allows_guarantee_letters else [],
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
        asks=asks_from(book, body.asks),
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
    asks: LinkAsks | None = None


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
    if body.asks is not None:
        link.asks = asks_from(book_of(db, link, link.owner, today(settings.org_timezone)), body.asks)
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
    """What the customer sees: who it's for, until when, and the medicines on offer.
    Never their prices: those come in the quotation letter, once the order is in."""
    link = open_link(db, token[:100])
    book = book_of(db, link, link.owner, today(settings.org_timezone))
    kind = book.price_type(link.price_type)
    products = []
    for p in book.products.values():
        price = book.prices.get(p.id, {}).get(link.price_type)
        if not price:
            continue
        products.append({"id": p.id, "code": p.code, "name": p.name, "genericName": p.generic_name, "strength": p.strength, "form": p.form, "unit": p.unit, "rx": p.needs_prescription})
    products.sort(key=lambda x: x["name"].lower())
    return {
        "company": company_of(request),
        "orgName": settings.org_name,
        "customer": link.company.name if link.company else None,
        "contact": link.contact.full_name if link.contact else None,
        # Not a customer yet: the page asks who they are before they send.
        "asksWho": link.company is None,
        "rep": link.owner.full_name,
        "expiresAt": iso(link.expires_at),
        "products": products,
        # What to send with the order, and how: straight to storage ("direct"), or with the order.
        "asks": asks_out(link),
        "uploads": "direct" if storage.configured(settings) else "with-order",
    }


class OrderLine(Api):
    product_id: str = Field(max_length=36)
    quantity: int = Field(ge=1, le=100_000)


class NewCustomer(Api):
    """Who's ordering, on a link for someone not a customer yet."""

    name: str = Field(min_length=2, max_length=160)
    contact_name: str | None = Field(None, max_length=160)
    mobile: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=254)
    # Where to deliver; the pin only if they chose to share their location.
    address: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=80)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)


# What an order sends besides its picks: files (uploaded straight to storage, or with the order) and the letter's details.
class FileRef(Api):
    kind: Literal["prescription", "letter", "document"]
    index: int = Field(0, ge=0, le=4)
    key: str = Field(min_length=1, max_length=300)
    name: str = Field("", max_length=120)


class LinkLetter(Api):
    number: str = Field(min_length=1, max_length=60)
    issued_on: date
    amount_centavos: int = Field(ge=1)


class OrderIn(Api):
    lines: list[OrderLine] = Field(min_length=1, max_length=50)
    note: str | None = Field(None, max_length=1000)
    customer: NewCustomer | None = None
    # Agreed to the privacy notice on the page: a medicine order is health
    # information, sensitive under the Data Privacy Act, so none is taken without it.
    privacy_accepted: bool = False
    # Uploaded straight to storage (app/storage.py): what each is, and where.
    files: list[FileRef] = Field(default_factory=list, max_length=12)
    # The guarantee letter's details, when the link asks for one.
    letter: LinkLetter | None = None


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
        address=(who.address or "").strip() or None,
        city=(who.city or "").strip() or None,
        latitude=who.latitude if who.latitude is not None and who.longitude is not None else None,
        longitude=who.longitude if who.latitude is not None and who.longitude is not None else None,
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


MAX_PRESCRIPTIONS = 3


def kept_upload(upload: UploadFile, field: str) -> tuple[dict, bytes]:
    """A file sent with the order, kept in the database: a PDF or a photo, told by its first bytes."""
    data = upload.file.read(storage.MAX_BYTES + 1)
    if len(data) > storage.MAX_BYTES:
        raise field_error(field, "A file is over 10 MB. Take the photo again at a lower size.")
    kind = next((v for magic, v in storage.KINDS.items() if data.startswith(magic)), None)
    if kind is None:
        raise field_error(field, "Attach a photo (JPG or PNG) or a PDF.")
    content_type, ext = kind
    return {"store": "db", "ref": secrets.token_hex(16), "name": (upload.filename or f"file{ext}")[:120], "contentType": content_type, "size": len(data)}, data


def kept_in_storage(settings, link: QuoteLink, ref: FileRef, field: str) -> dict:
    """A file the browser put in storage: only under this link's own folder, for this item, and really a PDF or a photo."""
    if not storage.configured(settings) or not ref.key.startswith(f"links/{link.id}/{ref.kind}-{ref.index}-"):
        raise field_error(field, "That file isn't this order's. Attach it again.")
    try:
        content_type, size = storage.check(settings, ref.key)
    except ValueError as e:
        raise field_error(field, {"missing": "The file didn't finish uploading. Attach it again.", "size": "A file is over 10 MB. Take the photo again at a lower size."}.get(str(e), "Attach a photo (JPG or PNG) or a PDF.")) from None
    return {"store": "s3", "key": ref.key, "name": (ref.name or ref.key.rsplit("/", 1)[-1])[:120], "contentType": content_type, "size": size}


class UploadAsk(Api):
    kind: Literal["prescription", "letter", "document"]
    index: int = Field(0, ge=0, le=4)
    content_type: Literal["application/pdf", "image/png", "image/jpeg"]


@router.post("/public/quote-links/{token}/uploads")
def upload_form(db: DB, settings: SettingsDep, token: str, body: UploadAsk) -> dict:
    """A signed form to upload one file the link asks for straight to storage: good
    for a few minutes, for one name in this link's folder, one kind, up to 10 MB."""
    link = open_link(db, token[:100])
    if not storage.configured(settings):
        raise HTTPException(status.HTTP_409_CONFLICT, "Files go with the order on this server.")
    asks = link.asks or {}
    if (body.kind == "letter" and not asks.get("payer")) or (body.kind == "document" and body.index >= len(asks.get("documents") or [])) or (body.kind == "prescription" and body.index >= MAX_PRESCRIPTIONS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "This link doesn't ask for that.")
    key = f"links/{link.id}/{body.kind}-{body.index}-{secrets.token_hex(8)}{storage.CONTENT_TYPES[body.content_type]}"
    return storage.presign_upload(settings, key, body.content_type)


@router.post("/public/quote-links/{token}", status_code=status.HTTP_201_CREATED)
def place_order(
    db: DB,
    settings: SettingsDep,
    token: str,
    order: Annotated[str, Form(max_length=20000)],
    prescription: Annotated[list[UploadFile], File()] = [],  # noqa: B006 (FastAPI's way of saying "none sent")
    letter_file: Annotated[UploadFile | None, File()] = None,
    document: Annotated[list[UploadFile], File()] = [],  # noqa: B006
) -> dict:
    """The customer's picks, made into a quote for them, the rep's. The link is used up.

    Sent as a form: `order` (the order, as JSON, with `files`: what was uploaded
    straight to storage). Where storage isn't set up, the files come in the form
    instead: `prescription` (up to 3), `letter_file`, and `document` (one per
    named document, in the link's order)."""
    try:
        body = extra_in = OrderIn.model_validate_json(order)
    except ValidationError as e:
        raise RequestValidationError([{**x, "loc": ("body", *x["loc"])} for x in e.errors(include_url=False)]) from None
    link = open_link(db, token[:100])
    company, contact, rep = link.company, link.contact, db.get(User, link.owner_id)
    if rep is None or not rep.is_active:
        raise HTTPException(status.HTTP_410_GONE, GONE)
    if not body.privacy_accepted:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "privacyAccepted"], "msg": "Agree to the privacy notice to send your order."}])
    if company is None and body.customer is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "customer", "name"], "msg": "Say who's ordering: your name, or your business's."}])
    if company is None and not ((body.customer.mobile or "").strip() or (body.customer.email or "").strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "customer", "mobile"], "msg": "Give a mobile number or an email, so your rep can reach you."}])
    book = book_of(db, link, rep, today(settings.org_timezone))
    kind = book.price_type(link.price_type)
    if kind is None:
        raise HTTPException(status.HTTP_410_GONE, GONE)
    seen: dict[str, int] = {}
    for line in body.lines:  # the same medicine twice is one line
        seen[line.product_id] = seen.get(line.product_id, 0) + line.quantity
    allowed = {pid for pid in book.products if book.prices.get(pid, {}).get(link.price_type)}
    if any(pid not in allowed for pid in seen):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "One of the medicines isn't offered on this link. Reload the page and pick again.")

    # What the link asks for, and what came: from storage (by name), or with the order.
    asks = link.asks or {}
    rx = sorted(book.products[pid].name for pid in seen if book.products[pid].needs_prescription)
    wants_prescription = bool(rx) or asks.get("prescription") == "always"
    issuer = next((i for i in book.issuers if i.code == asks.get("payer")), None) if asks.get("payer") and book.settings.allows_guarantee_letters else None
    labels = list(asks.get("documents") or [])
    in_db: list[tuple[dict, bytes]] = []  # kept in the database: (entry, bytes)
    prescriptions: list[dict] = []
    letter: dict | None = None
    documents: dict[int, dict] = {}
    for ref in extra_in.files:
        if ref.kind == "prescription" and len(prescriptions) < MAX_PRESCRIPTIONS:
            prescriptions.append(kept_in_storage(settings, link, ref, "prescription"))
        elif ref.kind == "letter" and issuer is not None:
            letter = kept_in_storage(settings, link, ref, "letterFile")
        elif ref.kind == "document" and ref.index < len(labels):
            documents[ref.index] = {"label": labels[ref.index], **kept_in_storage(settings, link, ref, f"documents.{ref.index}")}
    for upload in prescription[: MAX_PRESCRIPTIONS - len(prescriptions)]:
        entry, data = kept_upload(upload, "prescription")
        prescriptions.append(entry)
        in_db.append((entry, data))
    if letter_file is not None and letter_file.filename and issuer is not None and letter is None:
        letter, data = kept_upload(letter_file, "letterFile")
        in_db.append((letter, data))
    for i, upload in enumerate(document[: len(labels)]):
        if i not in documents and upload.filename:
            entry, data = kept_upload(upload, f"documents.{i}")
            documents[i] = {"label": labels[i], **entry}
            in_db.append((entry, data))
    if wants_prescription and not prescriptions:
        raise field_error("prescription", f"{', '.join(rx)} {'needs' if len(rx) == 1 else 'need'} a prescription: attach a photo of it." if rx else "Attach your prescription: a photo of it, or a PDF.")
    if issuer is not None and (letter is None or extra_in.letter is None):
        raise field_error("letterFile" if letter is None else "letter.number", f"Attach the {issuer.name} guarantee letter, with its number, date and the amount it covers.")
    for i, label in enumerate(labels):
        if i not in documents:
            raise field_error(f"documents.{i}", f"Attach your {label}.")

    agreed = datetime.now(UTC)
    sent = [f"prescription ({len(prescriptions)} {'file' if len(prescriptions) == 1 else 'files'})" if prescriptions else "", f"{issuer.name} guarantee letter" if issuer else "", *labels]
    sent = [x for x in sent if x]
    note = " ".join(x for x in (
        "Ordered by the customer through a link.",
        (body.note or "").strip(),
        f"Attached: {', '.join(sent)}." if sent else "",
        f"They agreed to the privacy notice on {agreed:%d %b %Y, %H:%M} UTC.",
    ) if x)
    quote = QuoteIn(
        price_type=kind.code,
        notes=note[:2000],
        lines=[LineIn(product_id=pid, quantity=qty) for pid, qty in seen.items()],
        payer=issuer.code if issuer else "self",
        letter=LetterIn(number=extra_in.letter.number, issued_on=extra_in.letter.issued_on, amount_centavos=extra_in.letter.amount_centavos) if issuer else None,
    )
    priced = with_tax(settings, book, price_lines(book, quote.price_type, quote.rx, [l.model_dump(by_alias=True) for l in quote.lines]))
    if company is None:
        # Now they're a customer: the rep's, priced as above.
        company, contact = customer_from(db, rep, body.customer)
        link.company_id, link.contact_id = company.id, contact.id if contact else None
    letter_data = next((d for e, d in in_db if e is letter), None)
    record = save_quote(db, settings, rep, company, contact, quote, priced, kind, issuer, None, check_extra(db, "quote", None), book.settings, letter, letter_data)
    for entry, data in in_db:
        if entry is not letter:  # the letter's own row is made by save_quote
            db.add(StoredFile(ref=entry["ref"], content_type=entry["contentType"], data=data))
    if prescriptions:
        # The quote is Rx: a pharmacist checks the prescription before it's ordered.
        record.prescriptions, record.rx = prescriptions, True
    if documents:
        record.documents = [documents[i] for i in sorted(documents)]
    link.used_at = datetime.now(UTC)
    link.privacy_accepted_at = agreed
    link.quote_id = record.id
    db.commit()
    # What they ordered, without prices: those come in the quotation letter.
    return {
        "number": record.number,
        "lines": [{"name": l.get("productName"), "quantity": l.get("quantity")} for l in record.lines],
        "waitsForApproval": record.approval_status == "pending",
        "rep": rep.full_name,
    }


class Spot(Api):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@router.post("/public/quote-links/{token}/place")
def place_of(db: DB, token: str, body: Spot) -> dict:
    """The address at a shared location, to fill in the delivery address: only for
    an open link (so it isn't a free lookup for anyone), in the Philippines. Nothing
    is kept here; the person checks it and sends it with the order."""
    open_link(db, token[:100])
    import httpx

    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": body.latitude, "lon": body.longitude, "format": "jsonv2", "zoom": 18, "addressdetails": 1, "accept-language": "en"},
            headers={"User-Agent": "BishnoiOne-CRM/1.0 (order links)"},
            timeout=8,
        )
        found = r.json().get("address", {}) if r.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        found = {}
    if found.get("country_code") not in (None, "ph"):
        return {"address": None, "city": None}
    street = " ".join(x for x in (found.get("house_number"), found.get("road")) if x)
    barangay = found.get("quarter") or found.get("suburb") or found.get("neighbourhood") or found.get("village") or found.get("hamlet")
    address = ", ".join(x for x in (street, f"Brgy. {barangay}" if barangay and not barangay.lower().startswith(("brgy", "barangay")) else barangay) if x) or None
    city = found.get("city") or found.get("town") or found.get("municipality") or found.get("county")
    return {"address": address, "city": city}
