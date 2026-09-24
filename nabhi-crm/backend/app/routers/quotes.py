"""Quotes: priced offers to a company, or to a contact.

- /companies/{id}/price-list, /contacts/{id}/price-list: what may be quoted.
- .../quotes/preview: what some lines come to. Nothing is saved.
- .../quotes (multipart): saves one. "quote" is the JSON; "letterFile" the
  guarantee letter, when DSWD, PCSO... pay.
- /quotes, /quotes/{id}, /quotes/{id}/letter: reading them; deleting one.
- /quotes/{id}/approval, /letter-check, /payments: the approver's decisions
  (quotes.approve).

A quote is priced with the customer's team's prices: its own where it set
them, the company's everywhere else. A quote is seen by whoever reaches it or
the customer it's for.
"""

import json
import secrets
from urllib.parse import quote as url_quote
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import Field, ValidationError, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, iso, not_found, person_out
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.extra import check_extra
from app.models import Company, Contact, Quote, StoredFile, Team, User
from app.pricing import Problems, price_book, price_lines, price_list_out, sales_settings, today
from app.scope import reaches, within

router = APIRouter(tags=["quotes"])

View = Annotated[Access, Depends(require("quotes.view"))]
Create = Annotated[Access, Depends(require("quotes.create"))]
Delete = Annotated[Access, Depends(require("quotes.delete"))]
Approve = Annotated[Access, Depends(require("quotes.approve"))]

MAX_LETTER_BYTES = 8 * 1024 * 1024
# What a letter may be, told by its first bytes rather than by what the browser claims.
LETTER_KINDS = {b"%PDF-": ("application/pdf", ".pdf"), b"\x89PNG\r\n\x1a\n": ("image/png", ".png"), b"\xff\xd8\xff": ("image/jpeg", ".jpg")}


# --- the request bodies ------------------------------------------------------------------


class Discount(Api):
    kind: Literal["percent", "amount"]
    value: int = Field(ge=1)


class LineIn(Api):
    """A product, or a bundle: a bundle is priced whole, so it takes only how many sets."""

    product_id: str | None = Field(None, max_length=36)
    bundle_id: str | None = Field(None, max_length=36)
    quantity: int = Field(ge=1, le=100_000)
    unit_price_centavos: int | None = Field(None, ge=1)
    promo_id: str | None = Field(None, max_length=36)
    discount: Discount | None = None

    @model_validator(mode="after")
    def _one(self) -> "LineIn":
        if bool(self.product_id) == bool(self.bundle_id):
            raise ValueError("Pick a product or a bundle.")
        return self


class LetterIn(Api):
    number: str = Field(min_length=1, max_length=60)
    issued_on: date
    amount_centavos: int = Field(ge=1)


class QuoteIn(Api):
    price_type: str = Field(min_length=1, max_length=40)
    rx: bool = False
    payer: str = Field("self", max_length=40)
    notes: str | None = Field(None, max_length=2000)
    lines: list[LineIn] = Field(min_length=1, max_length=50)
    letter: LetterIn | None = None
    # Added fields' values, by key (Settings → Forms).
    extra: dict[str, Any] | None = None


def lines_in(body: QuoteIn) -> list[dict]:
    return [l.model_dump(by_alias=True) for l in body.lines]


# --- whose quote, and who reaches it -----------------------------------------------------


def customer_of(db: Session, access: Access, kind: str, record_id: str) -> tuple[Company | None, Contact | None]:
    """The company, or the contact (and its company), a quote is made for."""
    if kind == "companies":
        company = db.get(Company, record_id)
        if company is None or not reaches(company, access):
            raise not_found("customer")
        return company, None
    contact = db.get(Contact, record_id)
    if contact is None or not reaches(contact, access):
        raise not_found("contact")
    return contact.company, contact


def pricing_team(company: Company | None, contact: Contact | None) -> str | None:
    """Whose prices apply: the team of whoever looks after the customer."""
    return (contact or company).team_id


def reachable(query, access: Access):
    """Quotes this person reaches: their own (by scope), or ones for a customer they reach."""
    if access.scope == "all":
        return query
    companies = within(select(Company.id), Company, access)
    contacts = within(select(Contact.id), Contact, access)
    mine = within(select(Quote.id), Quote, access)
    return query.where(or_(Quote.id.in_(mine), Quote.company_id.in_(companies), Quote.contact_id.in_(contacts)))


def reaches_quote(db: Session, quote: Quote, access: Access) -> bool:
    if reaches(quote, access):
        return True
    if quote.contact_id and (c := db.get(Contact, quote.contact_id)) and reaches(c, access):
        return True
    return bool(quote.company_id and (c := db.get(Company, quote.company_id)) and reaches(c, access))


def get_quote(db: Session, access: Access, quote_id: str) -> Quote:
    quote = db.get(Quote, quote_id)
    if quote is None or not reaches_quote(db, quote, access):
        raise not_found("quote")
    return quote


# --- what a quote looks like to the screens ----------------------------------------------


def state_of(q: Quote) -> str:
    if "rejected" in (q.approval_status, q.letter_status):
        return "rejected"
    if "pending" in (q.approval_status, q.letter_status):
        return "waiting"
    return "ready"


def by(person_id: str | None, name: str | None) -> dict | None:
    return {"id": person_id, "name": name} if name else None


def quote_out(db: Session, q: Quote, access: Access) -> dict:
    team = db.get(Team, q.team_id) if q.team_id else None
    company = db.get(Company, q.company_id) if q.company_id else None
    contact = db.get(Contact, q.contact_id) if q.contact_id else None
    letter = None
    if q.letter:
        f = q.letter.get("file")
        letter = {
            "number": q.letter["number"],
            "issuedOn": q.letter["issuedOn"],
            "amountCentavos": q.letter["amountCentavos"],
            "file": {"name": f["name"], "contentType": f["contentType"], "size": f["size"]} if f else None,
            "status": q.letter_status,
            "note": q.letter_note,
            "by": by(q.letter_by_id, q.letter_by_name),
            "at": iso(q.letter_at),
        }
    approver = access.can("quotes.approve")
    ready = state_of(q) == "ready"
    return {
        "id": q.id,
        "rev": None,
        "number": q.number,
        "team": q.team_id or "",
        "teamName": team.name if team else "No team",
        "company": {"id": company.id, "name": company.name} if company else None,
        "contact": {"id": contact.id, "name": contact.full_name} if contact else None,
        "customerId": (contact or company).id if (contact or company) else "",
        "customerHref": f"/contacts/{contact.id}" if contact else f"/companies/{company.id}" if company else None,
        "customerName": q.customer_name,
        "priceType": q.price_type,
        "priceTypeName": q.price_type_name,
        "rx": q.rx,
        "payer": q.payer,
        "payerName": q.payer_name,
        "notes": q.notes,
        "lines": q.lines,
        "grossCentavos": q.gross_centavos,
        "promoDiscountCentavos": q.promo_discount_centavos,
        "discountCentavos": q.discount_centavos,
        "totalCentavos": q.total_centavos,
        "state": state_of(q),
        "approval": {
            "status": q.approval_status,
            "reasons": q.approval_reasons,
            "note": q.approval_note,
            "by": by(q.approval_by_id, q.approval_by_name),
            "at": iso(q.approval_at),
        },
        "letter": letter,
        "payment": {"status": q.payment_status, "paidCentavos": q.paid_centavos, "payments": q.payments},
        "validUntil": q.valid_until,
        "terms": q.terms,
        "extra": q.extra or {},
        "createdAt": iso(q.created_at),
        "createdBy": person_out(q.created_by) or {"id": "", "name": "Someone no longer here"},
        "owner": person_out(db.get(User, q.owner_id)),
        "can": {
            "delete": access.can("quotes.delete") and q.paid_centavos == 0,
            "approve": approver and q.approval_status == "pending",
            "checkLetter": approver and q.letter_status == "pending",
            "recordPayment": approver and q.letter_status == "verified" and q.payment_status in ("unpaid", "partial") and ready,
            "order": ready and access.can("orders.create"),
        },
    }


# --- pricing -------------------------------------------------------------------------------

Kind = Literal["companies", "contacts"]


@router.get("/{kind}/{record_id}/price-list")
def read_price_list(access: View, db: DB, settings: SettingsDep, kind: Kind, record_id: str) -> dict:
    company, contact = customer_of(db, access, kind, record_id)
    return price_list_out(price_book(db, pricing_team(company, contact), today(settings.org_timezone)))


@router.post("/{kind}/{record_id}/quotes/preview")
def preview_quote(access: Create, db: DB, settings: SettingsDep, kind: Kind, record_id: str, body: QuoteIn) -> dict:
    company, contact = customer_of(db, access, kind, record_id)
    book = price_book(db, pricing_team(company, contact), today(settings.org_timezone))
    return price_lines(book, body.price_type, body.rx, lines_in(body))


def next_number(db: Session, on: str) -> str:
    prefix = f"{sales_settings(db).quote_prefix}-{on[:4]}{on[5:7]}-"
    last = db.scalar(select(func.max(Quote.number)).where(Quote.number.like(f"{prefix}%")))
    return f"{prefix}{(int(last.rsplit('-', 1)[1]) + 1 if last else 1):04d}"


async def read_letter(upload: UploadFile) -> tuple[bytes, str, str]:
    data = await upload.read(MAX_LETTER_BYTES + 1)
    problems = Problems()
    if len(data) > MAX_LETTER_BYTES:
        problems.add(["letterFile"], "The file is over 8 MB. Scan it at a lower resolution.")
    kind = next((v for magic, v in LETTER_KINDS.items() if data.startswith(magic)), None)
    if kind is None:
        problems.add(["letterFile"], "Attach the letter as a PDF, or a photo (JPG or PNG).")
    problems.raise_if_any()
    return data, kind[0], kind[1]


@router.post("/{kind}/{record_id}/quotes", status_code=status.HTTP_201_CREATED)
async def create_quote(
    access: Create,
    me: CurrentUser,
    db: DB,
    settings: SettingsDep,
    kind: Kind,
    record_id: str,
    quote: Annotated[str, Form(max_length=200_000)],
    letter_file: Annotated[UploadFile | None, File(alias="letterFile")] = None,
) -> dict:
    try:
        body = QuoteIn.model_validate(json.loads(quote))
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The quote wasn't readable. Reload and try again.") from None
    except ValidationError as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [{"type": x["type"], "loc": ["body", *x["loc"]], "msg": x["msg"]} for x in e.errors(include_url=False, include_context=False)],
        ) from None

    company, contact = customer_of(db, access, kind, record_id)
    on = today(settings.org_timezone)
    book = price_book(db, pricing_team(company, contact), on)
    priced = price_lines(book, body.price_type, body.rx, lines_in(body))
    kind_ = book.price_type(body.price_type)

    problems = Problems()
    if kind_.requires_notes and not body.notes:
        problems.add(["notes"], f"{kind_.name} needs notes: say why it applies.")
    issuer = None
    if body.payer != "self":
        issuer = next((i for i in book.issuers if i.code == body.payer), None) if book.settings.allows_guarantee_letters else None
        if issuer is None:
            problems.add(["payer"], "Pick who pays from the list.")
        elif body.letter is None:
            problems.add(["letter", "number"], "Enter the letter's number.")
        else:
            if body.letter.issued_on.isoformat() > on:
                problems.add(["letter", "issuedOn"], "The letter can't be dated after today.")
        if issuer is not None and (letter_file is None or not letter_file.filename):
            problems.add(["letterFile"], "Attach the letter: a PDF, or a photo (JPG or PNG).")
    problems.raise_if_any()
    extra = check_extra(db, "quote", body.extra)
    rules = book.settings

    stored = None
    if issuer is not None:
        data, content_type, ext = await read_letter(letter_file)
        ref = secrets.token_hex(16)
        name = Path(letter_file.filename).name[:120] or f"letter{ext}"
        stored = {"ref": ref, "ext": ext, "name": name, "contentType": content_type, "size": len(data)}

    who = (contact.full_name + (f", {company.name}" if company else "")) if contact else company.name
    reasons = priced["approvalReasons"]
    record = Quote(
        number=next_number(db, on),
        company_id=company.id if company else None,
        contact_id=contact.id if contact else None,
        customer_name=who[:200],
        price_type=kind_.code,
        price_type_name=kind_.name,
        rx=body.rx,
        payer=issuer.code if issuer else "self",
        payer_name=issuer.name if issuer else None,
        notes=body.notes,
        lines=priced["lines"],
        gross_centavos=priced["grossCentavos"],
        promo_discount_centavos=priced["promoDiscountCentavos"],
        discount_centavos=priced["discountCentavos"],
        total_centavos=priced["totalCentavos"],
        approval_status="pending" if reasons else "none",
        approval_reasons=reasons,
        letter=(
            {"number": body.letter.number, "issuedOn": body.letter.issued_on.isoformat(), "amountCentavos": body.letter.amount_centavos, "file": stored}
            if issuer
            else None
        ),
        letter_status="pending" if issuer else "none",
        payment_status="unpaid" if issuer else "none",
        payments=[],
        valid_until=(date.fromisoformat(on) + timedelta(days=rules.quote_valid_days)).isoformat(),
        terms=rules.quote_terms,
        extra=extra,
        owner_id=me.id,
        team_id=me.team_id,
        created_by_id=me.id,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:  # two quotes took the same number at once; the next one is free
        db.rollback()
        record.number = next_number(db, on)
        db.add(record)
        db.flush()
    if stored is not None:
        # Kept in the database, with the quote: saved together or not at all.
        db.add(StoredFile(ref=stored["ref"], content_type=stored["contentType"], data=data))
    audit(db, me, "quote.created", target=record.number, target_type="quote", target_id=record.id)
    db.commit()
    db.refresh(record)
    return quote_out(db, record, access)


# --- reading and deleting ------------------------------------------------------------------


@router.get("/quotes")
def list_quotes(
    access: View,
    db: DB,
    company: str | None = Query(None, max_length=36),
    contact: str | None = Query(None, max_length=36),
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    task: Literal["approvals", "letters", "payments"] | None = Query(None, description="what's waiting on an approver"),
    state: Literal["waiting", "ready", "rejected"] | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    query = reachable(select(Quote), access)
    if company:
        query = query.where(Quote.company_id == company)
    if contact:
        query = query.where(Quote.contact_id == contact)
    if owner:
        query = query.where(Quote.owner_id == (access.user_id if owner == "me" else owner))
    if task == "approvals":
        query = query.where(Quote.approval_status == "pending")
    elif task == "letters":
        query = query.where(Quote.letter_status == "pending")
    elif task == "payments":
        query = query.where(Quote.letter_status == "verified", Quote.payment_status.in_(("unpaid", "partial")), Quote.approval_status.in_(("none", "approved")))
    if state == "rejected":
        query = query.where(or_(Quote.approval_status == "rejected", Quote.letter_status == "rejected"))
    elif state == "waiting":
        query = query.where(
            Quote.approval_status != "rejected", Quote.letter_status != "rejected", or_(Quote.approval_status == "pending", Quote.letter_status == "pending")
        )
    elif state == "ready":
        query = query.where(Quote.approval_status.in_(("none", "approved")), Quote.letter_status.in_(("none", "verified")))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Quote.number).like(like), func.lower(Quote.customer_name).like(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    quotes = db.scalars(query.order_by(Quote.created_at.desc()).limit(limit).offset(offset)).unique().all()
    return {"items": [quote_out(db, x, access) for x in quotes], "total": total}


@router.get("/quotes/{quote_id}")
def read_quote(access: View, db: DB, quote_id: str) -> dict:
    return quote_out(db, get_quote(db, access, quote_id), access)


def letter_file_of(db: Session, quote: Quote) -> StoredFile | None:
    f = (quote.letter or {}).get("file")
    return db.get(StoredFile, f["ref"]) if f else None


@router.get("/quotes/{quote_id}/letter")
def read_letter_file(access: View, db: DB, quote_id: str) -> Response:
    quote = get_quote(db, access, quote_id)
    stored = letter_file_of(db, quote)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This quote has no letter on file.")
    name = quote.letter["file"]["name"]
    return Response(
        stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f"inline; filename*=utf-8''{url_quote(name)}"},
    )


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quote(access: Delete, me: CurrentUser, db: DB, quote_id: str) -> Response:
    quote = get_quote(db, access, quote_id)
    if quote.paid_centavos:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payments are recorded on this quote, so it stays.")
    stored = letter_file_of(db, quote)
    audit(db, me, "quote.deleted", target=quote.number, target_type="quote", target_id=quote.id)
    if stored is not None:
        db.delete(stored)
    db.delete(quote)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the approver's decisions --------------------------------------------------------------


class Decision(Api):
    decision: Literal["approve", "reject"]
    note: str | None = Field(None, max_length=1000)


def decided(body: Decision) -> None:
    if body.decision == "reject" and not body.note:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Say why it's rejected: the rep sees your reason on the quote.")


@router.post("/quotes/{quote_id}/approval")
def decide_approval(access: Approve, me: CurrentUser, db: DB, quote_id: str, body: Decision) -> dict:
    quote = get_quote(db, access, quote_id)
    if quote.approval_status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "This quote isn't waiting for approval.")
    decided(body)
    quote.approval_status = "approved" if body.decision == "approve" else "rejected"
    quote.approval_note, quote.approval_by_id, quote.approval_by_name, quote.approval_at = body.note, me.id, me.full_name, datetime.now(UTC)
    audit(db, me, f"quote.{quote.approval_status}", target=quote.number, target_type="quote", target_id=quote.id)
    db.commit()
    return quote_out(db, quote, access)


@router.post("/quotes/{quote_id}/letter-check")
def check_letter(access: Approve, me: CurrentUser, db: DB, quote_id: str, body: Decision) -> dict:
    quote = get_quote(db, access, quote_id)
    if quote.letter_status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "This quote's letter isn't waiting to be checked.")
    decided(body)
    quote.letter_status = "verified" if body.decision == "approve" else "rejected"
    quote.letter_note, quote.letter_by_id, quote.letter_by_name, quote.letter_at = body.note, me.id, me.full_name, datetime.now(UTC)
    audit(db, me, f"quote.letter_{quote.letter_status}", target=quote.number, target_type="quote", target_id=quote.id)
    db.commit()
    return quote_out(db, quote, access)


class PaymentIn(Api):
    paid_on: date
    # None: whatever the letter still has to pay.
    amount_centavos: int | None = Field(None, ge=1)
    reference: str | None = Field(None, max_length=80)


@router.post("/quotes/{quote_id}/payments")
def record_payment(access: Approve, me: CurrentUser, db: DB, settings: SettingsDep, quote_id: str, body: PaymentIn) -> dict:
    quote = get_quote(db, access, quote_id)
    if not quote_out(db, quote, access)["can"]["recordPayment"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payments are recorded once the letter is verified and the quote approved, until it's paid.")
    left = quote.letter["amountCentavos"] - quote.paid_centavos
    amount = body.amount_centavos or left
    problems = Problems()
    if amount > left:
        problems.add(["amountCentavos"], "More than the letter still has to pay.")
    if body.paid_on.isoformat() > today(settings.org_timezone):
        problems.add(["paidOn"], "A payment can't be dated after today.")
    problems.raise_if_any()
    now = datetime.now(UTC)
    payment = {"id": secrets.token_hex(8), "paidOn": body.paid_on.isoformat(), "amountCentavos": amount, "reference": body.reference, "byName": me.full_name, "at": now.isoformat()}
    quote.payments = [*quote.payments, payment]
    quote.paid_centavos += amount
    quote.payment_status = "paid" if quote.paid_centavos >= quote.letter["amountCentavos"] else "partial"
    if quote.payment_status == "paid":
        quote.paid_at = now
    audit(db, me, "quote.payment_recorded", target=quote.number, target_type="quote", target_id=quote.id)
    db.commit()
    return quote_out(db, quote, access)
