"""Finance's desk: the quotes that need Finance.

- approvals: quotes with a price type that needs approval (Special Price...)
  or manual discounts over the division's limit;
- letters: DSWD, PCSO... guarantee letters to check against the file;
- payments: what the issuer has paid on a verified letter.

Finance spans divisions: its grants reach every sales division's teams, and
every read and write here is scoped to exactly those grants, like the sales
workspace. Viewing needs Finance "view"; deciding and recording payments need
Finance "edit".
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cached_property
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access
from app.audit import audit
from app.deps import DB, CurrentAccess, CurrentUser, FilesDep, RecordsDep
from app.money import money
from app.models import Profile, Subdivision
from app.catalogue import sales_keys
from app.modules import BY_KEY
from app.quotes import QUOTE, letter_response, quote_out
from app.schemas import DecisionIn, PaymentIn
from app.scope import Scope
from app.store.query import Eq, In, Query
from app.store.records import Patch, Records


router = APIRouter(prefix="/finance", tags=["finance"])

FINANCE = "finance"
Task = Literal["approvals", "letters", "payments"]

# task -> (open filter, done filter, open order, done order)
TASKS: dict[str, tuple[tuple, tuple, tuple, tuple]] = {
    "approvals": (
        (Eq("approvalStatus", "pending"),),
        (In("approvalStatus", ("approved", "rejected")),),
        (("createdAt", "asc"),),
        (("approvalAt", "desc"),),
    ),
    "letters": (
        (Eq("letterStatus", "pending"),),
        (In("letterStatus", ("verified", "rejected")),),
        (("createdAt", "asc"),),
        (("letterAt", "desc"),),
    ),
    "payments": (
        (Eq("letterStatus", "verified"), In("paymentStatus", ("unpaid", "partial"))),
        (Eq("paymentStatus", "paid"),),
        (("letterAt", "asc"),),
        (("paidAt", "desc"),),
    ),
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class Desk:
    user: Profile
    access: Access
    db: Session
    records: Records

    def scopes(self, action: str) -> frozenset[Scope]:
        # Quotes live in the sales divisions; that's all Finance reaches here.
        return frozenset(s for s in self.access.scopes(FINANCE, action) if s.division in sales_keys(self.db))

    def visible(self) -> frozenset[Scope]:
        scopes = self.scopes("view")
        if not scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to Finance.")
        return scopes

    def can(self, action: str, scope: Scope) -> bool:
        return self.access.can_in(FINANCE, action, scope)

    def quote(self, quote_id: str) -> dict:
        doc = self.records.get(QUOTE, quote_id, self.visible())
        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That quote doesn't exist, or it's outside what you can see.")
        return doc

    def editable(self, quote_id: str) -> dict:
        doc = self.quote(quote_id)
        if not self.can("edit", Scope.of(doc)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can see this quote but not act on it.")
        return doc

    @cached_property
    def team_names(self) -> dict[tuple[str, str], str]:
        rows = self.db.execute(select(Subdivision.division_code, Subdivision.code, Subdivision.name))
        return {(d, c): n for d, c, n in rows.all()}

    def customer_names(self, docs: list[dict]) -> dict[str, str]:
        ids = tuple({d["customerId"] for d in docs})
        if not ids:
            return {}
        hits = self.records.find(Query("customer", self.visible(), (In("_id", ids),), limit=len(ids)))
        return {h["_id"]: h["name"] for h in hits}

    def out(self, doc: dict, names: dict[str, str] | None = None) -> dict:
        scope = Scope.of(doc)
        edit = self.can("edit", scope)
        return quote_out(
            doc,
            division_name=BY_KEY[scope.division].name if scope.division in BY_KEY else scope.division,
            team_name=self.team_names.get((scope.division, scope.subdivision), scope.subdivision),
            customer_name=(names or {}).get(doc["customerId"]),
            can={
                "approve": edit and doc.get("approvalStatus") == "pending",
                "checkLetter": edit and doc.get("letterStatus") == "pending",
                "recordPayment": edit
                and doc.get("letterStatus") == "verified"
                and doc.get("paymentStatus") in ("unpaid", "partial"),
            },
        )


def get_desk(user: CurrentUser, access: CurrentAccess, db: DB, records: RecordsDep) -> Desk:
    return Desk(user, access, db, records)


DeskDep = Annotated[Desk, Depends(get_desk)]


@router.get("/summary")
def summary(desk: DeskDep) -> dict:
    scopes = desk.visible()
    return {
        "counts": {task: desk.records.count(Query(QUOTE, scopes, where)) for task, (where, *_rest) in TASKS.items()},
    }


@router.get("/quotes")
def list_quotes(desk: DeskDep, task: Task, state: Literal["open", "done"] = "open") -> dict:
    open_where, done_where, open_order, done_order = TASKS[task]
    where, order = (open_where, open_order) if state == "open" else (done_where, done_order)
    docs = desk.records.find(Query(QUOTE, desk.visible(), where, order, limit=200 if state == "open" else 50))
    names = desk.customer_names(docs)
    return {"items": [desk.out(d, names) for d in docs]}


@router.get("/quotes/{quote_id}")
def get_quote(desk: DeskDep, quote_id: str) -> dict:
    doc = desk.quote(quote_id)
    return desk.out(doc, desk.customer_names([doc]))


@router.get("/quotes/{quote_id}/letter")
def quote_letter(desk: DeskDep, files: FilesDep, quote_id: str) -> Response:
    return letter_response(desk.quote(quote_id), files)


def decide(desk: Desk, prefix: str, status_value: str, note: str | None) -> dict:
    return {
        f"{prefix}Status": status_value,
        f"{prefix}Note": note,
        f"{prefix}ById": desk.user.id,
        f"{prefix}ByName": desk.user.full_name,
        f"{prefix}At": now_iso(),
    }


def commit_decision(desk: Desk, doc: dict, changes: dict) -> dict:
    to_set = {k: v for k, v in changes.items() if v is not None}
    to_unset = tuple(k for k, v in changes.items() if v is None)
    # Pinned to the revision read, so two people deciding at once can't both win.
    desk.records.commit([Patch(doc["_id"], to_set, to_unset, if_revision=doc["_rev"])])
    updated = desk.quote(doc["_id"])
    return desk.out(updated, desk.customer_names([updated]))


@router.post("/quotes/{quote_id}/approval")
def approve_quote(desk: DeskDep, quote_id: str, body: DecisionIn) -> dict:
    doc = desk.editable(quote_id)
    if doc.get("approvalStatus") != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "This quote isn't waiting for approval any more.")
    result = "approved" if body.decision == "approve" else "rejected"
    out = commit_decision(desk, doc, decide(desk, "approval", result, body.note))
    audit(desk.db, desk.user, f"quote.{result}", doc["number"])
    return out


@router.post("/quotes/{quote_id}/letter-check")
def check_letter(desk: DeskDep, quote_id: str, body: DecisionIn) -> dict:
    doc = desk.editable(quote_id)
    if doc.get("letterStatus") != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "This guarantee letter has already been checked.")
    result = "verified" if body.decision == "approve" else "rejected"
    out = commit_decision(desk, doc, decide(desk, "letter", result, body.note))
    audit(desk.db, desk.user, f"quote.letter_{result}", doc["number"])
    return out


@router.post("/quotes/{quote_id}/payments", status_code=status.HTTP_201_CREATED)
def record_payment(desk: DeskDep, quote_id: str, body: PaymentIn) -> dict:
    doc = desk.editable(quote_id)
    if doc.get("letterStatus") != "verified":
        raise HTTPException(status.HTTP_409_CONFLICT, "Check the guarantee letter before recording payments on it.")
    letter_amount = doc["letter"]["amountCentavos"]
    paid = doc.get("paidCentavos", 0)
    if paid + body.amount_centavos > letter_amount:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [{
                "type": "value_error",
                "loc": ["body", "amountCentavos"],
                "msg": f"Only {money(desk.db, letter_amount - paid)} is left on this letter.",
            }],
        )
    paid += body.amount_centavos
    payment_id = uuid.uuid4().hex
    payment = {
        "_key": payment_id,  # Sanity wants a key on every object in an array
        "id": payment_id,
        "paidOn": body.paid_on.isoformat(),
        "amountCentavos": body.amount_centavos,
        "reference": body.reference,
        "byId": desk.user.id,
        "byName": desk.user.full_name,
        "at": now_iso(),
    }
    changes = {
        "payments": [*doc.get("payments", []), {k: v for k, v in payment.items() if v is not None}],
        "paidCentavos": paid,
        "paymentStatus": "paid" if paid >= letter_amount else "partial",
        "paidAt": now_iso() if paid >= letter_amount else None,
    }
    out = commit_decision(desk, doc, changes)
    audit(desk.db, desk.user, "quote.payment_recorded", doc["number"], ["amountCentavos", "paidOn", "reference"])
    return out

