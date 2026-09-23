"""Bulk actions: one request for many records, worked through by the job queue
(app/jobs.py).

Each endpoint checks what it can up front (the body, that the person may do
this at all, the person things are being given to) and answers 202 with the
job. The work then runs batch by batch: within the request when it fits in one
batch, in the background otherwise. Every batch opens its own database session
and reloads the person's access, so switching someone off, or taking a grant
away, stops their job at the next batch. Every item is checked on its own:
that it's visible, that the action is allowed in its team, and that it still
needs doing.

A batch's changes go to the records store in one transaction. If the store
refuses it because something changed meanwhile, the batch is retried one
record at a time, so only the records that changed fail.
"""

import logging
from collections.abc import Callable, Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.access import Access, access_for_everyone, active_member, load_access
from app.audit import audit
from app.deps import DB, CurrentAccess, CurrentUser, FilesDep
from app.errors import field_errors
from app.jobs import JobQueue, Outcome
from app.money import money
from app.models import Product, Profile, utcnow
from app.quotes import QUOTE, letter_file_ref
from app.routers.finance import Desk, DeskDep, decide
from app.routers.inventory import INVENTORY, list_price_codes
from app.routers.sales import CHILD_TYPES, CUSTOMER, FOLLOW_UP, WS, Workspace, follow_up_doc, now_iso
from app.schemas import (
    MAX_CENTAVOS,
    CustomersBulkIn,
    CustomersDeleteBulk,
    CustomersFollowUpBulk,
    CustomersOwnerBulk,
    CustomersStatusBulk,
    DecisionsBulkIn,
    FollowUpsBulkIn,
    ProductsBulkIn,
)
from app.scope import Scope
from app.store.files import FileStore
from app.store.query import MAX_LIMIT, In, Query
from app.store.records import ConflictError, Create, Delete, Mutation, Patch, Records, StoreError
from app.tenancy import company_of, set_company

log = logging.getLogger("crm.bulk")

router = APIRouter(tags=["bulk actions"])

MISSING = "Not found, or it's in a team you can't see."
NOT_ALLOWED = "You don't have permission to change this one."
CHANGED = "Someone changed this meanwhile. Reload and try again."
NOT_SAVED = "Couldn't save this one. Try again in a minute."
SWITCHED_OFF = "Your account was switched off, so this wasn't done."

# A plan for one record: what to commit, or why not, or None when there's nothing to do.
Plan = list[Mutation] | str | None


def get_jobs(request: Request) -> JobQueue:
    return request.app.state.jobs


def get_sessions(request: Request) -> sessionmaker:
    return request.app.state.sessions


JobsDep = Annotated[JobQueue, Depends(get_jobs)]
SessionsDep = Annotated[sessionmaker, Depends(get_sessions)]


# --- the machinery ---------------------------------------------------------------------


def as_person(
    sessions: sessionmaker,
    org_id: str,
    user_id: str,
    ids: list[str],
    fn: Callable[[Session, Profile, Access], list[Outcome]],
) -> list[Outcome]:
    """Runs one batch as the person who asked, in their company, with their access as it is now."""
    with sessions() as db:
        set_company(db, org_id)
        user = db.get(Profile, user_id)
        if user is None or not user.is_active or active_member(db, user_id) is None:
            return [(i, SWITCHED_OFF) for i in ids]
        try:
            return fn(db, user, load_access(db, user_id))
        except HTTPException as exc:  # lost access to the whole workspace mid-job
            message = exc.detail if isinstance(exc.detail, str) else NOT_ALLOWED
            return [(i, message) for i in ids]


def load_many(desk: Workspace | Desk, doc_type: str, ids: Sequence[str]) -> dict[str, dict]:
    docs = desk.records.find(Query(doc_type, desk.visible(), (In("_id", tuple(ids)),), limit=len(ids)))
    return {d["_id"]: d for d in docs}


def commit_items(records: Records, items: list[tuple[str, list[Mutation]]]) -> list[Outcome]:
    """One transaction for the batch; if something in it changed meanwhile, one per record."""
    if not items:
        return []
    try:
        records.commit([m for _, mutations in items for m in mutations])
        return [(item_id, None) for item_id, _ in items]
    except ConflictError:
        pass
    except StoreError:
        log.exception("bulk batch of %d not saved", len(items))
        return [(item_id, NOT_SAVED) for item_id, _ in items]
    outcomes: list[Outcome] = []
    for item_id, mutations in items:
        try:
            records.commit(mutations)
            outcomes.append((item_id, None))
        except ConflictError:
            outcomes.append((item_id, CHANGED))
        except StoreError:
            outcomes.append((item_id, NOT_SAVED))
    return outcomes


def apply_each(
    desk: Workspace | Desk, found: dict[str, dict], ids: list[str], action: str, plan: Callable[[dict], Plan]
) -> list[Outcome]:
    outcomes: list[Outcome] = []
    items: list[tuple[str, list[Mutation]]] = []
    for item_id in ids:
        doc = found.get(item_id)
        if doc is None:
            outcomes.append((item_id, MISSING))
        elif not desk.can(action, Scope.of(doc)):
            outcomes.append((item_id, NOT_ALLOWED))
        else:
            result = plan(doc)
            if isinstance(result, str):
                outcomes.append((item_id, result))
            elif result:
                items.append((item_id, result))
            else:
                outcomes.append((item_id, None))  # already so
    return outcomes + commit_items(desk.records, items)


def person_in_divisions(db: Session, divisions: tuple[str, ...], user_id: str) -> Profile:
    """Checked up front: someone who can see at least one of these divisions.
    Each record's own team is checked again per record, by can_see below."""
    entry = access_for_everyone(db).get(user_id)
    if entry is None or not any(entry[1].scopes(d, "view") for d in divisions):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That person can't see these customers.")
    return entry[0]


def can_see(everyone: dict[str, tuple[Profile, Access]], user_id: str, scope: Scope) -> Profile | None:
    """Against the record's own division, since a batch may span several."""
    entry = everyone.get(user_id)
    return entry[0] if entry and entry[1].can_in(scope.division, "view", scope) else None


def require_somewhere(ws: Workspace, action: str) -> None:
    ws.visible()
    if not ws.scopes(action):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that here.")


# --- sales: customers --------------------------------------------------------------------


def customers_status(ws: Workspace, body: CustomersStatusBulk, ids: list[str]) -> list[Outcome]:
    stamp = now_iso()

    def plan(doc: dict) -> Plan:
        if doc["status"] == body.status:
            return None
        return [Patch(doc["_id"], {"status": body.status, "updatedAt": stamp}, if_revision=doc["_rev"])]

    return apply_each(ws, load_many(ws, CUSTOMER, ids), ids, "edit", plan)


def customers_owner(ws: Workspace, body: CustomersOwnerBulk, ids: list[str]) -> list[Outcome]:
    everyone = access_for_everyone(ws.db)
    stamp = now_iso()

    def plan(doc: dict) -> Plan:
        owner = can_see(everyone, body.owner_id, Scope.of(doc))
        if owner is None:
            return "The new owner can't see this customer's team."
        if doc.get("ownerId") == owner.id:
            return None
        changes = {"ownerId": owner.id, "ownerName": owner.full_name, "updatedAt": stamp}
        return [Patch(doc["_id"], changes, if_revision=doc["_rev"])]

    return apply_each(ws, load_many(ws, CUSTOMER, ids), ids, "edit", plan)


def customers_follow_up(ws: Workspace, body: CustomersFollowUpBulk, ids: list[str]) -> list[Outcome]:
    everyone = access_for_everyone(ws.db)
    assignee_id = body.follow_up.assignee_id or ws.user.id
    stamp = now_iso()

    def plan(doc: dict) -> Plan:
        scope = Scope.of(doc)
        who = doc.get("ownerId") if body.to_owner and doc.get("ownerId") else assignee_id
        assignee = can_see(everyone, who, scope)
        if assignee is None:
            return "That person can't see this customer's team."
        follow_up = follow_up_doc(ws, scope, doc["_id"], body.follow_up, assignee)
        # Touching the customer at the revision read ties the follow-up to its current team.
        return [Create(follow_up), Patch(doc["_id"], {"updatedAt": stamp}, if_revision=doc["_rev"])]

    return apply_each(ws, load_many(ws, CUSTOMER, ids), ids, "create", plan)


def children_of(ws: Workspace, customers: list[dict]) -> dict[str, list[dict]]:
    """Everything filed under these customers, fetched per type rather than per customer."""
    by_customer: dict[str, list[dict]] = {c["_id"]: [] for c in customers}
    if not customers:
        return by_customer
    scopes = frozenset(Scope.of(c) for c in customers)
    ids = tuple(by_customer)
    for doc_type in CHILD_TYPES:
        offset = 0
        while True:
            page = ws.records.find(Query(doc_type, scopes, (In("customerId", ids),), (("_id", "asc"),), offset, MAX_LIMIT))
            for child in page:
                by_customer[child["customerId"]].append(child)
            if len(page) < MAX_LIMIT:
                break
            offset += MAX_LIMIT
    return by_customer


def customers_delete(ws: Workspace, files: FileStore, ids: list[str]) -> list[Outcome]:
    found = load_many(ws, CUSTOMER, ids)
    children = children_of(ws, [d for d in found.values() if ws.can("delete", Scope.of(d))])
    stamp = now_iso()

    def plan(doc: dict) -> Plan:
        # The guard fails this customer's delete if it changed since it was read.
        guard = Patch(doc["_id"], {"updatedAt": stamp}, if_revision=doc["_rev"])
        return [guard, *(Delete(c["_id"]) for c in children[doc["_id"]]), Delete(doc["_id"])]

    outcomes = apply_each(ws, found, ids, "delete", plan)
    for item_id, error in outcomes:
        if error is None and item_id in children:
            for child in children[item_id]:
                if ref := letter_file_ref(child):
                    files.delete(ref)
    return outcomes


LABELS = {
    "status": "Change status",
    "owner": "Change owner",
    "follow_up": "Add follow-ups",
    "delete": "Delete customers",
}
NEEDS = {"status": "edit", "owner": "edit", "follow_up": "create", "delete": "delete"}


@router.post("/sales/bulk/customers", status_code=status.HTTP_202_ACCEPTED)
def bulk_customers(ws: WS, jobs: JobsDep, sessions: SessionsDep, files: FilesDep, body: CustomersBulkIn) -> dict:
    require_somewhere(ws, NEEDS[body.action])
    if isinstance(body, CustomersOwnerBulk):
        person_in_divisions(ws.db, ws.divisions, body.owner_id)
    if isinstance(body, CustomersFollowUpBulk) and body.follow_up.assignee_id:
        person_in_divisions(ws.db, ws.divisions, body.follow_up.assignee_id)
    divisions, records, settings, user_id = ws.divisions, ws.records, ws.settings, ws.user.id
    org_id = company_of(ws.db)

    def batch(db: Session, user: Profile, access: Access, ids: list[str]) -> list[Outcome]:
        batch_ws = Workspace(divisions, user, access, db, records, settings)
        if isinstance(body, CustomersStatusBulk):
            return customers_status(batch_ws, body, ids)
        if isinstance(body, CustomersOwnerBulk):
            return customers_owner(batch_ws, body, ids)
        if isinstance(body, CustomersFollowUpBulk):
            return customers_follow_up(batch_ws, body, ids)
        return customers_delete(batch_ws, files, ids)

    def work(ids: list[str]) -> list[Outcome]:
        return as_person(sessions, org_id, user_id, ids, lambda db, user, access: batch(db, user, access, ids))

    audit(ws.db, ws.user, f"bulk.customers.{body.action}", f"{len(body.ids)} customers in {', '.join(divisions)}")
    # A customer's delete carries everything filed under it; smaller batches keep each transaction small.
    size = 20 if isinstance(body, CustomersDeleteBulk) else None
    return jobs.submit(user_id, LABELS[body.action], body.ids, work, batch_size=size).out()


# --- sales: follow-ups -------------------------------------------------------------------


def follow_ups(ws: Workspace, body: FollowUpsBulkIn, ids: list[str]) -> list[Outcome]:
    everyone = access_for_everyone(ws.db) if body.action == "assign" else {}
    stamp = now_iso()

    def plan(doc: dict) -> Plan:
        done = doc["status"] == "done"
        to_set: dict = {}
        to_unset: tuple[str, ...] = ()
        if body.action == "done":
            if done:
                return None
            to_set = {"status": "done", "doneAt": stamp, "doneById": ws.user.id, "doneByName": ws.user.full_name}
        elif body.action == "open":
            if not done:
                return None
            to_set, to_unset = {"status": "open"}, ("doneAt", "doneById", "doneByName")
        elif body.action == "due":
            if done:
                return "It's already done. Reopen it to move it."
            due = body.due_on.isoformat() if body.due_on else None
            if doc["dueOn"] == due:
                return None
            to_set = {"dueOn": due}
        else:
            person = can_see(everyone, body.assignee_id or "", Scope.of(doc))
            if person is None:
                return "That person can't see this follow-up's team."
            if doc.get("assigneeId") == person.id:
                return None
            to_set = {"assigneeId": person.id, "assigneeName": person.full_name}
        return [Patch(doc["_id"], to_set, to_unset)]

    return apply_each(ws, load_many(ws, FOLLOW_UP, ids), ids, "edit", plan)


FOLLOW_UP_LABELS = {"done": "Mark done", "open": "Reopen", "due": "Move due date", "assign": "Reassign"}


@router.post("/sales/bulk/follow-ups", status_code=status.HTTP_202_ACCEPTED)
def bulk_follow_ups(ws: WS, jobs: JobsDep, sessions: SessionsDep, body: FollowUpsBulkIn) -> dict:
    require_somewhere(ws, "edit")
    if body.action == "assign" and body.assignee_id:
        person_in_divisions(ws.db, ws.divisions, body.assignee_id)
    divisions, records, settings, user_id = ws.divisions, ws.records, ws.settings, ws.user.id
    org_id = company_of(ws.db)

    def work(ids: list[str]) -> list[Outcome]:
        return as_person(
            sessions,
            org_id,
            user_id,
            ids,
            lambda db, user, access: follow_ups(Workspace(divisions, user, access, db, records, settings), body, ids),
        )

    audit(ws.db, ws.user, f"bulk.follow_ups.{body.action}", f"{len(body.ids)} follow-ups in {', '.join(divisions)}")
    return jobs.submit(user_id, FOLLOW_UP_LABELS[body.action], body.ids, work).out()


# --- finance: approvals ---------------------------------------------------------------------
# Only approvals. Checking a guarantee letter means looking at each letter, and
# a payment is an amount per letter, so those stay one at a time.


def approvals(desk: Desk, body: DecisionsBulkIn, ids: list[str]) -> list[Outcome]:
    result = "approved" if body.decision == "approve" else "rejected"

    def plan(doc: dict) -> Plan:
        if doc.get("approvalStatus") != "pending":
            return "It isn't waiting for approval any more."
        changes = decide(desk, "approval", result, body.note)
        to_set = {k: v for k, v in changes.items() if v is not None}
        to_unset = tuple(k for k, v in changes.items() if v is None)
        # Pinned to the revision read, so two people deciding at once can't both win.
        return [Patch(doc["_id"], to_set, to_unset, if_revision=doc["_rev"])]

    return apply_each(desk, load_many(desk, QUOTE, ids), ids, "edit", plan)


@router.post("/finance/bulk/approvals", status_code=status.HTTP_202_ACCEPTED)
def bulk_approvals(desk: DeskDep, jobs: JobsDep, sessions: SessionsDep, body: DecisionsBulkIn) -> dict:
    desk.visible()
    if not desk.scopes("edit"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can see Finance's tasks but not act on them.")
    records, user_id = desk.records, desk.user.id
    org_id = company_of(desk.db)

    def work(ids: list[str]) -> list[Outcome]:
        return as_person(sessions, org_id, user_id, ids, lambda db, user, access: approvals(Desk(user, access, db, records), body, ids))

    audit(desk.db, desk.user, f"bulk.quotes.{body.decision}", f"{len(body.ids)} quotes")
    label = "Approve quotes" if body.decision == "approve" else "Reject quotes"
    return jobs.submit(user_id, label, body.ids, work).out()


# --- inventory: products ----------------------------------------------------------------------


def repriced(amount: int, change_bp: int) -> int:
    """The new price, rounded to the nearest centavo (half up)."""
    return (amount * (10_000 + change_bp) + 5_000) // 10_000


def products(db: Session, access: Access, body: ProductsBulkIn, ids: list[str]) -> list[Outcome]:
    if not access.can(INVENTORY, "edit"):
        return [(i, NOT_ALLOWED) for i in ids]
    found = {
        p.id: p
        for p in db.scalars(select(Product).where(Product.id.in_(ids)).options(selectinload(Product.prices)))
    }
    outcomes: list[Outcome] = []
    changed = False
    for product_id in ids:
        product = found.get(product_id)
        if product is None:
            outcomes.append((product_id, "No such product."))
            continue
        if body.action in ("activate", "deactivate"):
            wanted = body.action == "activate"
            if product.is_active != wanted:
                product.is_active, changed = wanted, True
            outcomes.append((product_id, None))
            continue
        prices = [x for x in product.prices if body.price_type in (None, x.price_type_code)]
        if not prices:
            outcomes.append((product_id, "It has no price of that type to change."))
            continue
        new = {x.price_type_code: repriced(x.amount_centavos, body.change_bp or 0) for x in prices}
        if any(amount > MAX_CENTAVOS for amount in new.values()):
            outcomes.append((product_id, f"That would take a price over {money(db, MAX_CENTAVOS)}."))
            continue
        for x in prices:
            x.amount_centavos = new[x.price_type_code]
        product.updated_at = utcnow()
        changed = True
        outcomes.append((product_id, None))
    if changed:
        db.commit()
    return outcomes


PRODUCT_LABELS = {"activate": "Switch on", "deactivate": "Switch off", "reprice": "Change prices"}


@router.post("/inventory/bulk/products", status_code=status.HTTP_202_ACCEPTED)
def bulk_products(
    access: CurrentAccess, me: CurrentUser, db: DB, jobs: JobsDep, sessions: SessionsDep, body: ProductsBulkIn
) -> dict:
    access.require(INVENTORY, "edit")
    if body.action == "reprice" and body.price_type and body.price_type not in list_price_codes(db):
        raise field_errors([(("priceType",), "That isn't a price-list price.")])
    user_id = me.id
    org_id = company_of(db)

    def work(ids: list[str]) -> list[Outcome]:
        return as_person(sessions, org_id, user_id, ids, lambda db, user, access: products(db, access, body, ids))

    audit(db, me, f"bulk.products.{body.action}", f"{len(body.ids)} products")
    return jobs.submit(user_id, PRODUCT_LABELS[body.action], body.ids, work).out()


# --- progress ----------------------------------------------------------------------------------


@router.get("/jobs/{job_id}")
def job_progress(job_id: str, me: CurrentUser, jobs: JobsDep) -> dict:
    job = jobs.get(job_id, me.id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That job is finished and forgotten, or isn't yours.")
    return job.out()
