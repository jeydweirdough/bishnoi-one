"""Sales invoices (benchmarks decision D4): made out to the CRM's customers,
worked out by the tax engine, numbered from the BIR's authority, and posted
to the ledger.

    draft ──issue──> issued ──void──> void
      │ edited, deleted      never edited: voided, keeping its number

Issuing takes the next number of a series (an ATP's range), works the
invoice out once more and keeps that answer as the invoice forever, and posts
what the customer owes against the sale and its tax. Voiding posts the
reversal; the number stays used, as the BIR expects every number accounted for.

Permissions: invoices.view to read, .create for drafts, .issue, .void, and
.setup for the number series.
"""

import re
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import business_events
from app.access import access_of, permitted
from app.audit import audit
from app.crm import CrmUnavailable, find_customers, read_customer
from app.deps import DB, SettingsDep
from app.funds import RELEASE_METHODS as METHODS
from app.ledger import Leg, account, money_account, post
from app.ledger import settings as posting_settings
from app.locks import locked
from app.models import Invoice, InvoicePayment, InvoiceSeries, JournalEntry
from app.routers.funds import today
from app.routers.tax import (
    Api,
    BuyerBody,
    LineBody,
    SaleBody,
    field_error,
    iso,
    work_out,
)

router = APIRouter(prefix="/finance/invoices", tags=["invoices"])


# --- number series ---------------------------------------------------------------------------


class SeriesIn(Api):
    name: str = Field(min_length=1, max_length=80)
    prefix: str = Field("", max_length=10)
    digits: int = Field(6, ge=1, le=12)
    first_number: int = Field(ge=1)
    last_number: int = Field(ge=1)
    atp_number: str = Field(min_length=1, max_length=40)
    atp_date: date


class SeriesPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    is_active: bool | None = None


def formatted(s: InvoiceSeries, n: int) -> str:
    return f"{s.prefix}{n:0{s.digits}d}"


def series_out(s: InvoiceSeries) -> dict:
    return {
        "id": s.id, "name": s.name, "prefix": s.prefix, "digits": s.digits,
        "firstNumber": formatted(s, s.first_number), "lastNumber": formatted(s, s.last_number),
        "nextNumber": formatted(s, s.next_number) if s.left else None, "left": s.left,
        "atpNumber": s.atp_number, "atpDate": s.atp_date.isoformat(), "isActive": s.is_active,
    }


def usable_series(db: Session) -> list[InvoiceSeries]:
    """Switched on, with numbers left: what an invoice can be issued from."""
    rows = db.scalars(select(InvoiceSeries).where(InvoiceSeries.is_active).order_by(InvoiceSeries.created_at)).all()
    return [s for s in rows if s.left]


@router.get("/series")
def list_series(user: permitted("invoices.view"), db: DB, settings: SettingsDep) -> dict:
    rows = db.scalars(select(InvoiceSeries).order_by(InvoiceSeries.is_active.desc(), InvoiceSeries.created_at)).all()
    # crmLinked: whether the invoice form can find customers in the CRM.
    return {"items": [series_out(s) for s in rows], "canSetup": access_of(user).can("invoices.setup"), "crmLinked": settings.crm_linked}


@router.post("/series", status_code=status.HTTP_201_CREATED)
def add_series(user: permitted("invoices.setup"), db: DB, body: SeriesIn) -> dict:
    if body.last_number < body.first_number:
        raise field_error("lastNumber", "The last number can't be before the first.")
    # Two series printing the same number would be two invoices with one number.
    for other in db.scalars(select(InvoiceSeries).where(InvoiceSeries.prefix == body.prefix)):
        if body.first_number <= other.last_number and other.first_number <= body.last_number:
            raise field_error("firstNumber", f"These numbers overlap the series \"{other.name}\" ({formatted(other, other.first_number)} to {formatted(other, other.last_number)}).")
    s = InvoiceSeries(**body.model_dump(), next_number=body.first_number)
    db.add(s)
    db.flush()
    audit(db, user, "series.created", target=f"{s.name} ({s.atp_number})", target_type="invoice_series", target_id=s.id)
    db.commit()
    return series_out(s)


@router.patch("/series/{series_id}")
def change_series(user: permitted("invoices.setup"), db: DB, series_id: str, body: SeriesPatch) -> dict:
    s = db.get(InvoiceSeries, series_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such series.")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(s, k, v)
    audit(db, user, "series.updated", target=f"{s.name} ({s.atp_number})", target_type="invoice_series", target_id=s.id, fields=changes.keys())
    db.commit()
    return series_out(s)


# --- customers, from the CRM -----------------------------------------------------------------


@router.get("/customers")
def customers(_: permitted("invoices.create"), settings: SettingsDep, q: str | None = Query(None, max_length=100)) -> dict:
    try:
        return {"items": find_customers(settings, q)}
    except CrmUnavailable as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None


# --- invoices ----------------------------------------------------------------------------------


class InvoiceIn(Api):
    customer_id: str | None = Field(None, max_length=36)
    customer_name: str = Field(min_length=1, max_length=200)
    customer_tin: str | None = Field(None, max_length=20)
    customer_address: str | None = Field(None, max_length=300)
    salesperson_id: str | None = Field(None, max_length=36)
    salesperson_name: str | None = Field(None, max_length=120)
    # The salesperson's division and team, as the CRM gives them with the customer's owner.
    division_id: str | None = Field(None, max_length=36)
    division_name: str | None = Field(None, max_length=120)
    team_id: str | None = Field(None, max_length=36)
    team_name: str | None = Field(None, max_length=120)
    treatment: str = Field("regular", max_length=20)
    buyer_id_number: str | None = Field(None, max_length=40)
    invoice_date: date
    terms_days: int = Field(30, ge=0, le=365)
    reference: str | None = Field(None, max_length=80)
    notes: str | None = Field(None, max_length=500)
    prices_include_tax: bool | None = None
    lines: list[LineBody] = Field(min_length=1, max_length=500)


def sale_of(inv: Invoice) -> SaleBody:
    return SaleBody(
        treatment=inv.treatment,
        on=inv.invoice_date,
        prices_include_tax=inv.prices_include_tax,
        buyer=BuyerBody(name=inv.customer_name, tin=inv.customer_tin, address=inv.customer_address, id_number=inv.buyer_id_number),
        lines=[LineBody(**line) for line in inv.lines],
    )


def tax_of(computed: dict) -> int:
    return next((s["amountCentavos"] for s in computed["summary"] if s["key"] == "tax"), 0)


def links(db: Session, invoices: list[Invoice]) -> dict[str, dict]:
    """For each invoice, what it replaces and what replaced it (cancel and reissue),
    worked out for a whole list at once. Shown on screens and lists, never printed."""
    ids = [i.id for i in invoices]
    olds = {i.replaces_id for i in invoices if i.replaces_id}
    found_old = {o.id: o for o in db.scalars(select(Invoice).where(Invoice.id.in_(olds)))} if olds else {}
    newer = {n.replaces_id: n for n in db.scalars(select(Invoice).where(Invoice.replaces_id.in_(ids)))} if ids else {}
    out = {}
    for i in invoices:
        old, new = found_old.get(i.replaces_id), newer.get(i.id)
        out[i.id] = {
            "replaces": {"id": old.id, "number": old.number, "voidedAt": iso(old.voided_at), "reason": old.void_reason} if old else None,
            "replacedBy": {"id": new.id, "number": new.number, "status": new.status} if new else None,
        }
    return out


# Where a problem the tax step found is, in the words of the invoice form (and the
# form's field, so it can be highlighted there).
PROBLEM_PLACES = {
    ("buyer", "tin"): ("Customer's TIN", "customerTin"),
    ("buyer", "idNumber"): ("ID number", "buyerIdNumber"),
    ("buyer", "name"): ("Customer", "customerName"),
    ("buyer", "address"): ("Address", "customerAddress"),
    ("treatment",): ("Buyer type", "treatment"),
}
LINE_PARTS = {"category": "VAT", "quantity": "quantity", "unitPriceCentavos": "unit price", "discountCentavos": "discount"}


def readable(detail) -> tuple[str, dict[str, str]]:
    """What the tax step said, as sentences saying where ("Customer's TIN: ...",
    "Line 2: ..."), and the form fields to mark. It used to say only "Some lines
    need fixing", even when it was the customer's TIN (fixed 2026-10-22)."""
    if isinstance(detail, str):
        return detail, {}
    said, fields = [], {}
    for d in detail if isinstance(detail, list) else []:
        loc = [p for p in d.get("loc", []) if p != "body"]
        msg = str(d.get("msg", "")).removeprefix("Value error, ")
        if loc[:1] == ["lines"] and len(loc) >= 2 and str(loc[1]).isdigit():
            n = int(loc[1])
            part = LINE_PARTS.get(str(loc[2])) if len(loc) > 2 else None
            label, key = f"Line {n + 1}" + (f" ({part})" if part else ""), f"lines.{n}.{loc[2]}" if len(loc) > 2 else "lines"
        else:
            label, key = PROBLEM_PLACES.get(tuple(loc), (" ".join(map(str, loc)) or "This invoice", ".".join(map(str, loc))))
        said.append(f"{label}: {msg}")
        fields[key] = msg
    return (" ".join(said) or "This draft can't be worked out yet: edit it and check each field."), fields


def cost_lines(db: Session, settings, inv: Invoice) -> tuple[list | None, int]:
    """Each line's cost per unit from Inventory (by its item code), and the invoice's total cost."""
    from app.inventory import unit_costs

    if not (posting_settings(db).cogs_account_id and posting_settings(db).inventory_account_id):
        return None, 0
    lines = inv.lines or []
    costs = unit_costs(settings, [str(l.get("ref") or "") for l in lines])
    if costs is None:
        return None, 0
    per_unit = [costs.get(str(l.get("ref") or "").strip().upper()) for l in lines]
    return per_unit, sum((c or 0) * int(l.get("quantity") or 0) for c, l in zip(per_unit, lines))


def invoice_out(db: Session, inv: Invoice, settings, *, full: bool = True, linked: dict | None = None) -> dict:
    due = inv.invoice_date + timedelta(days=inv.terms_days)
    out = {
        "id": inv.id, "status": inv.status, "number": inv.number,
        "customer": {"id": inv.customer_id, "name": inv.customer_name, "tin": inv.customer_tin, "address": inv.customer_address},
        "salesperson": {"id": inv.salesperson_id, "name": inv.salesperson_name} if inv.salesperson_id or inv.salesperson_name else None,
        "division": {"id": inv.division_id, "name": inv.division_name} if inv.division_name else None,
        "team": {"id": inv.team_id, "name": inv.team_name} if inv.team_name else None,
        "treatment": inv.treatment, "buyerIdNumber": inv.buyer_id_number,
        "date": inv.invoice_date.isoformat(), "termsDays": inv.terms_days, "dueDate": due.isoformat(),
        "reference": inv.reference, "notes": inv.notes, "pricesIncludeTax": inv.prices_include_tax,
        "totalCentavos": inv.total_centavos, "taxCentavos": inv.tax_centavos, "paidCentavos": inv.paid_centavos,
        "balanceCentavos": inv.total_centavos - inv.paid_centavos if inv.status == "issued" else 0,
        "createdBy": inv.created_by, "createdAt": iso(inv.created_at),
        "issuedBy": inv.issued_by, "issuedAt": iso(inv.issued_at),
        "voidedBy": inv.voided_by, "voidedAt": iso(inv.voided_at), "voidReason": inv.void_reason,
        "series": {"id": inv.series.id, "name": inv.series.name, "atpNumber": inv.series.atp_number, "atpDate": inv.series.atp_date.isoformat(),
                   "range": f"{formatted(inv.series, inv.series.first_number)} to {formatted(inv.series, inv.series.last_number)}"} if inv.series else None,
    }
    out |= linked if linked is not None else links(db, [inv])[inv.id]
    # Every listing carries the payments (loaded with the invoices, no extra queries): the
    # Sales list opens a row in place to show them (2026-10-25).
    out["payments"] = [payment_out(p) for p in inv.payments]
    if full:
        out["lines"] = inv.lines
        out["entryId"] = inv.entry_id
        out["methods"] = [{"key": k, "label": v} for k, v in METHODS.items()]
        # A draft is worked out afresh each time it's read; an issued one is as it was issued.
        out["problemFields"] = {}
        if inv.computed is not None:
            out["computed"], out["problem"] = inv.computed, None
        else:
            try:
                out["computed"], out["problem"] = work_out(db, settings, sale_of(inv)), None
            except HTTPException as e:
                out["computed"] = None
                out["problem"], out["problemFields"] = readable(e.detail)
    return out


def found(db: Session, invoice_id: str) -> Invoice:
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such invoice.")
    return inv


def must_be_draft(inv: Invoice) -> None:
    if inv.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "An issued invoice isn't changed: void it and make a new one.")


def fill(inv: Invoice, body: InvoiceIn, settings) -> None:
    if body.invoice_date > today(settings):
        raise field_error("invoiceDate", "An invoice can't be dated in the future.")
    for k, v in body.model_dump(exclude={"lines"}).items():
        setattr(inv, k, v)
    inv.lines = [line.model_dump(mode="json", by_alias=True) for line in body.lines]


@router.get("")
def list_invoices(
    _: permitted("invoices.view"),
    db: DB,
    settings: SettingsDep,
    status_: str | None = Query(None, alias="status", max_length=10),
    q: str | None = Query(None, max_length=100),
    customer: str | None = Query(None, max_length=36),
    limit: int = Query(200, ge=1, le=500),
) -> dict:
    query = select(Invoice).order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc()).limit(limit)
    if status_ in ("draft", "issued", "void"):
        query = query.where(Invoice.status == status_)
    if customer:
        query = query.where(Invoice.customer_id == customer)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Invoice.customer_name).like(like), func.lower(Invoice.number).like(like), func.lower(Invoice.reference).like(like)))
    counts = dict(db.execute(select(Invoice.status, func.count()).group_by(Invoice.status)).all())
    rows = list(db.scalars(query))
    linked = links(db, rows)
    return {
        "items": [invoice_out(db, i, settings, full=False, linked=linked[i.id]) for i in rows],
        "counts": {k: counts.get(k, 0) for k in ("draft", "issued", "void")},
        "figures": month_figures(db, settings),
        # How a payment can be made, for Record payment on an opened row.
        "methods": [{"key": k, "label": v} for k, v in METHODS.items()],
    }


def month_figures(db: Session, settings) -> dict:
    """The Sales list's two headline figures, this month and last: what was invoiced (issued, not
    void, by invoice date) and what was collected (payments by the day paid, removed ones left out)."""
    now = today(settings)
    first = now.replace(day=1)
    before = (first - timedelta(days=1)).replace(day=1)

    def invoiced(start: date, end: date) -> int:
        return int(db.scalar(select(func.coalesce(func.sum(Invoice.total_centavos), 0)).where(
            Invoice.status == "issued", Invoice.invoice_date >= start, Invoice.invoice_date < end)) or 0)

    def collected(start: date, end: date) -> int:
        return int(db.scalar(select(func.coalesce(func.sum(InvoicePayment.amount_centavos), 0)).where(
            InvoicePayment.removed_at.is_(None), InvoicePayment.paid_on >= start, InvoicePayment.paid_on < end)) or 0)

    return {
        "invoicedCentavos": invoiced(first, now + timedelta(days=1)), "invoicedLastMonthCentavos": invoiced(before, first),
        "collectedCentavos": collected(first, now + timedelta(days=1)), "collectedLastMonthCentavos": collected(before, first),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def add_invoice(user: permitted("invoices.create"), db: DB, settings: SettingsDep, body: InvoiceIn) -> dict:
    inv = Invoice(created_by=user.full_name, lines=[])
    fill(inv, body, settings)
    db.add(inv)
    db.flush()
    audit(db, user, "invoice.drafted", target=inv.customer_name, target_type="invoice", target_id=inv.id)
    db.commit()
    return invoice_out(db, inv, settings)


@router.get("/{invoice_id}")
def read_invoice(_: permitted("invoices.view"), db: DB, settings: SettingsDep, invoice_id: str) -> dict:
    return invoice_out(db, found(db, invoice_id), settings)


@router.put("/{invoice_id}")
def change_invoice(user: permitted("invoices.create"), db: DB, settings: SettingsDep, invoice_id: str, body: InvoiceIn) -> dict:
    inv = found(db, invoice_id)
    must_be_draft(inv)
    fill(inv, body, settings)
    audit(db, user, "invoice.updated", target=inv.customer_name, target_type="invoice", target_id=inv.id)
    db.commit()
    return invoice_out(db, inv, settings)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(user: permitted("invoices.create"), db: DB, invoice_id: str) -> Response:
    inv = found(db, invoice_id)
    must_be_draft(inv)
    audit(db, user, "invoice.deleted", target=inv.customer_name, target_type="invoice", target_id=inv.id)
    db.delete(inv)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class IssueIn(Api):
    series_id: str | None = Field(None, max_length=36)


@router.post("/{invoice_id}/issue")
def issue(user: permitted("invoices.issue"), db: DB, settings: SettingsDep, invoice_id: str, body: IssueIn) -> dict:
    inv = found(db, invoice_id)
    must_be_draft(inv)
    # The customer's TIN, when the CRM has it and the draft doesn't.
    if inv.customer_id and not inv.customer_tin and settings.crm_linked:
        try:
            inv.customer_tin = read_customer(settings, inv.customer_id).get("tin") or None
        except CrmUnavailable:
            pass
    computed = work_out(db, settings, sale_of(inv))
    if computed["warnings"]:
        raise HTTPException(status.HTTP_409_CONFLICT, " ".join(computed["warnings"]) + " Go to Tax, Registration, then issue it.")
    # The series, locked while its number is taken, so two invoices issued at once never share one.
    options = usable_series(db)
    s = next((x for x in options if x.id == body.series_id), None) if body.series_id else (options[0] if options else None)
    if s is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "There are no invoice numbers left to issue from. Add the series from the BIR's Authority to Print under Invoices, Invoice numbers.")
    [s] = locked(db, InvoiceSeries, [s.id])  # also on SQLite, where FOR UPDATE alone locks nothing
    if not s.left:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The series \"{s.name}\" has run out of numbers. Add the next Authority to Print's series.")
    inv.number = formatted(s, s.next_number)
    s.next_number += 1
    inv.series, inv.status = s, "issued"
    inv.computed = computed
    inv.total_centavos, inv.tax_centavos = computed["totalDueCentavos"], tax_of(computed)
    inv.issued_at, inv.issued_by = datetime.now(UTC), user.full_name
    ledger = posting_settings(db)
    old = db.get(Invoice, inv.replaces_id) if inv.replaces_id else None
    replacing = f", replacing {old.number}" if old else ""
    legs = [
        Leg(account(db, ledger.receivables_account_id), debit=inv.total_centavos),
        Leg(account(db, ledger.sales_account_id), credit=inv.total_centavos - inv.tax_centavos),
        Leg(account(db, ledger.output_tax_account_id), credit=inv.tax_centavos),
    ]
    # The cost of goods sold, from Inventory by each line's item code, in the same entry: a void
    # reverses the sale and its cost together (decided 2026-10-28). Not linked, or no codes: no cost.
    inv.line_costs, inv.cost_centavos = cost_lines(db, settings, inv)
    if inv.cost_centavos and ledger.cogs_account_id and ledger.inventory_account_id:
        legs += [
            Leg(account(db, ledger.cogs_account_id), debit=inv.cost_centavos, description="Cost of goods sold"),
            Leg(account(db, ledger.inventory_account_id), credit=inv.cost_centavos, description="Cost of goods sold"),
        ]
    entry = post(db, inv.invoice_date, f"{inv.number}: sale to {inv.customer_name}{replacing}", legs, user.full_name, reference=inv.number, source="invoice")
    inv.entry_id = entry.id
    audit(db, user, "invoice.issued", target=f"{inv.number} {inv.customer_name}", target_type="invoice", target_id=inv.id)
    # Told to the other apps (step 7): the CRM scores sales from it.
    business_events.emit(db, None, "invoice.issued", {"id": inv.id, "number": inv.number, "customerId": inv.customer_id, "customerName": inv.customer_name, "salespersonId": inv.salesperson_id, "divisionId": inv.division_id, "teamId": inv.team_id, "date": inv.invoice_date.isoformat(), "totalCentavos": inv.total_centavos, "taxCentavos": inv.tax_centavos})
    db.commit()
    return invoice_out(db, inv, settings)


class VoidIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/{invoice_id}/void")
def void(user: permitted("invoices.void"), db: DB, settings: SettingsDep, invoice_id: str, body: VoidIn) -> dict:
    inv = found(db, invoice_id)
    locked(db, Invoice, [inv.id])  # a payment saved at the same moment is either seen or waits; never both
    cancel(db, settings, user, inv, body.reason)
    business_events.emit(db, None, "invoice.voided", {**{"id": inv.id, "number": inv.number, "customerId": inv.customer_id, "customerName": inv.customer_name, "salespersonId": inv.salesperson_id, "divisionId": inv.division_id, "teamId": inv.team_id, "date": inv.invoice_date.isoformat(), "totalCentavos": inv.total_centavos, "taxCentavos": inv.tax_centavos}, "reason": body.reason})
    db.commit()
    return invoice_out(db, inv, settings)


def cancel(db: Session, settings, user, inv: Invoice, reason: str) -> None:
    """Void an issued invoice: its entry reversed, its number kept, the reason recorded."""
    if inv.status != "issued":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an issued invoice is voided. A draft is simply deleted.")
    if inv.paid_centavos:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payments are recorded against this invoice: take them off first.")
    entry = db.get(JournalEntry, inv.entry_id) if inv.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of {inv.number}: {reason}", legs, user.full_name, reference=inv.number, source="invoice", reverses=entry)
    inv.status, inv.void_reason = "void", reason
    inv.voided_at, inv.voided_by = datetime.now(UTC), user.full_name
    audit(db, user, "invoice.voided", target=f"{inv.number} {inv.customer_name}", target_type="invoice", target_id=inv.id)


class ReissueIn(Api):
    # Needed when cancelling an issued invoice; a cancelled one already has its reason.
    reason: str | None = Field(None, min_length=3, max_length=300)


@router.post("/{invoice_id}/reissue", status_code=status.HTTP_201_CREATED)
def reissue(user: permitted("invoices.create"), db: DB, settings: SettingsDep, invoice_id: str, body: ReissueIn) -> dict:
    """Cancel and reissue (Rommel Q20: a posted invoice is never edited). An issued
    invoice is voided exactly as Void does, and a draft copying it is made, marked as
    its replacement, dated today (changeable before issuing). A cancelled invoice with
    no replacement yet gets just the draft. Answers the new draft, to correct and issue."""
    inv = found(db, invoice_id)
    if inv.status == "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "A draft is changed directly: there's nothing to reissue.")
    if inv.status == "issued":
        if not access_of(user).can("invoices.void"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow voiding invoices.")
        if not body.reason:
            raise field_error("reason", "Say why it's cancelled (at least 3 characters).")
        cancel(db, settings, user, inv, body.reason)
    taken = db.scalar(select(Invoice).where(Invoice.replaces_id == inv.id))
    if taken is not None:
        what = f"{taken.number}" if taken.number else "a draft"
        raise HTTPException(status.HTTP_409_CONFLICT, f"{inv.number} is already being replaced by {what}. Open that one, or delete the draft first.")
    copy = Invoice(
        created_by=user.full_name, replaces_id=inv.id, invoice_date=today(settings),
        customer_id=inv.customer_id, customer_name=inv.customer_name, customer_tin=inv.customer_tin, customer_address=inv.customer_address,
        salesperson_id=inv.salesperson_id, salesperson_name=inv.salesperson_name,
        division_id=inv.division_id, division_name=inv.division_name, team_id=inv.team_id, team_name=inv.team_name, treatment=inv.treatment, buyer_id_number=inv.buyer_id_number,
        terms_days=inv.terms_days, reference=inv.reference, notes=inv.notes, prices_include_tax=inv.prices_include_tax,
        lines=[dict(line) for line in inv.lines],
    )
    db.add(copy)
    db.flush()
    audit(db, user, "invoice.reissued", target=f"{inv.number} {inv.customer_name}", target_type="invoice", target_id=copy.id, fields=[inv.number])
    # The chain (step 9): the voided invoice, then the one replacing it (numbered when it's issued).
    business_events.link(db, None, business_events.ref("invoice", inv.id, inv.number), business_events.ref("invoice", copy.id, None))
    db.commit()
    return invoice_out(db, copy, settings)


# --- payments ---------------------------------------------------------------------------------


def payment_out(p: InvoicePayment) -> dict:
    return {
        "id": p.id, "paidOn": p.paid_on.isoformat(), "amountCentavos": p.amount_centavos,
        "method": p.method, "methodLabel": METHODS.get(p.method, p.method), "reference": p.reference,
        "cwtCentavos": p.cwt_centavos, "cwtAtc": p.cwt_atc, "cwtCertificate": p.cwt_certificate,
        "recordedBy": p.recorded_by, "recordedAt": iso(p.recorded_at),
        "removedBy": p.removed_by, "removedAt": iso(p.removed_at),
    }


class PaymentIn(Api):
    paid_on: date
    amount_centavos: int = Field(ge=1)
    method: str = Field(max_length=10)
    reference: str | None = Field(None, max_length=80)
    # What the customer withheld and paid the BIR for us (their Form 2307), on top of the money received.
    cwt_centavos: int = Field(0, ge=0)
    cwt_atc: str | None = Field(None, max_length=8)
    cwt_certificate: str | None = Field(None, max_length=60)


@router.post("/{invoice_id}/payments", status_code=status.HTTP_201_CREATED)
def record_payment(user: permitted("invoices.collect"), db: DB, settings: SettingsDep, invoice_id: str, body: PaymentIn) -> dict:
    """Money received: cash in, what the customer owes down."""
    inv = found(db, invoice_id)
    # Locked and read again before any check: two payments at once can't both fit in what was owed.
    locked(db, Invoice, [inv.id])
    if inv.status != "issued":
        raise HTTPException(status.HTTP_409_CONFLICT, "Payments are recorded against an issued invoice.")
    if body.method not in METHODS:
        raise field_error("method", "Pick how it was paid.")
    if body.paid_on > today(settings):
        raise field_error("paidOn", "A payment can't be dated in the future.")
    if body.paid_on < inv.invoice_date:
        raise field_error("paidOn", "A payment can't come before the invoice.")
    owed = inv.total_centavos - inv.paid_centavos
    settled = body.amount_centavos + body.cwt_centavos
    if settled > owed:
        raise field_error("amountCentavos", f"That's more than is owed on this invoice ({owed / 100:,.2f}), withholding included.")
    atc = (body.cwt_atc or "").strip().upper() or None
    if body.cwt_centavos and not atc:
        raise field_error("cwtAtc", "Give the ATC the customer's Form 2307 shows (e.g. WC158).")
    if atc and not re.fullmatch(r"W[A-Z]\d{3}[A-Z]?", atc):
        raise field_error("cwtAtc", "An ATC looks like WC158 or WI160, as on the Form 2307.")
    ledger = posting_settings(db)
    p = InvoicePayment(invoice=inv, paid_on=body.paid_on, amount_centavos=body.amount_centavos, method=body.method, reference=body.reference, recorded_by=user.full_name,
                       cwt_centavos=body.cwt_centavos, cwt_atc=atc if body.cwt_centavos else None, cwt_certificate=(body.cwt_certificate or "").strip() or None)
    how = METHODS[body.method] + (f" ({body.reference})" if body.reference else "")
    # The withholding settles the invoice as the money does: 1210 Creditable withholding tax, credited against our income tax.
    entry = post(db, body.paid_on, f"{inv.number}: payment from {inv.customer_name}, {how}", [
        Leg(money_account(db, body.method), debit=body.amount_centavos),
        *([Leg(account(db, ledger.cwt_account_id), debit=body.cwt_centavos, description=f"Withheld by the customer ({atc})")] if body.cwt_centavos else []),
        Leg(account(db, ledger.receivables_account_id), credit=settled),
    ], user.full_name, reference=body.reference or inv.number, source="invoice")
    p.entry_id = entry.id
    inv.paid_centavos += settled
    db.add(p)
    db.flush()
    audit(db, user, "invoice.paid", target=f"{inv.number} {inv.customer_name}", target_type="invoice", target_id=inv.id)
    business_events.emit(db, None, "payment.recorded", {
        "invoiceId": inv.id, "number": inv.number, "customerId": inv.customer_id, "paidOn": body.paid_on.isoformat(),
        "amountCentavos": settled, "paidCentavos": inv.paid_centavos, "totalCentavos": inv.total_centavos})
    db.commit()
    return invoice_out(db, inv, settings)


@router.delete("/{invoice_id}/payments/{payment_id}")
def remove_payment(user: permitted("invoices.void"), db: DB, settings: SettingsDep, invoice_id: str, payment_id: str) -> dict:
    """A payment recorded by mistake: its entry reversed, the line kept and marked."""
    inv = found(db, invoice_id)
    locked(db, Invoice, [inv.id])  # taken off twice at once: the second sees it already taken off
    [p] = locked(db, InvoicePayment, [payment_id]) or [None]
    if p is None or p.invoice_id != inv.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such payment.")
    if p.removed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "This payment was already taken off.")
    entry = db.get(JournalEntry, p.entry_id) if p.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"{inv.number}: payment taken off", legs, user.full_name, reference=entry.reference, source="invoice", reverses=entry)
    p.removed_at, p.removed_by = datetime.now(UTC), user.full_name
    inv.paid_centavos -= p.amount_centavos + p.cwt_centavos
    audit(db, user, "invoice.payment_removed", target=f"{inv.number} {inv.customer_name}", target_type="invoice", target_id=inv.id)
    db.commit()
    return invoice_out(db, inv, settings)


def issued_to_nobody(db: Session) -> int:
    """For the sidebar: 1 when no invoice can be issued for want of numbers."""
    return 0 if usable_series(db) else 1

