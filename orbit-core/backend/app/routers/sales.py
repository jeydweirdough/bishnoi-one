"""The sales workspace: customers, activities (calls, visits, messages, notes),
follow-ups and quotes. One set of endpoints serves all six sales divisions; the
`module` path segment picks the division, and every read and write is scoped
to the teams the caller has in it.

Records that belong to a customer (activities, follow-ups, quotes) take the
customer's scope. The client never sends a scope for them, so they can't drift
apart.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import cached_property
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query as Param, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access import Access, access_for_everyone
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentAccess, CurrentUser, FilesDep, RecordsDep, SettingsDep
from app.errors import field_errors
from app.fields import check_values
from app.catalogue import sales_keys
from app.lists import codes
from app.models import Division, Headquarters, Product, Profile, Subdivision
from app.modules import ORDERS
from app.price_book import (
    load_bundles,
    load_issuers,
    load_price_types,
    load_products,
    load_promos,
    load_rules,
    load_team_prices,
)
from app.pricing import SELF, PricedQuote, PricingError, price_quote
from app.quotes import QUOTE, finance_has_acted, letter_file_ref, letter_response, priced_out, quote_doc, quote_out, state
from app.schemas import ActivityIn, CustomerIn, CustomerPatch, FollowUpIn, FollowUpPatch, QuoteIn, phone_digits
from app.scope import Scope, is_code
from app.store.files import MAX_LETTER_BYTES, sniff
from app.store.query import MAX_LIMIT, Cmp, Eq, In, Query, Search
from app.store.records import ConflictError, Create, Delete, Patch, Records
from app.tenancy import org_get


router = APIRouter(prefix="/sales", tags=["sales workspace"])

CUSTOMER, ACTIVITY, FOLLOW_UP = "customer", "activity", "followUp"
CHILD_TYPES = (ACTIVITY, FOLLOW_UP, QUOTE)
CUSTOMER_TEXT_FIELDS = ("specialty", "phone", "email", "address", "city", "notes")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def today(settings: Settings) -> str:
    return today_date(settings).isoformat()


def today_date(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def new_id() -> str:
    return str(uuid.uuid4())



def a_choice(db: Session, kind: str, value: str | None, loc: str, what: str) -> None:
    """Refuse a code this company doesn't keep. A record that already carries a
    switched-off choice stays valid; only new values must be an active one."""
    if value is not None and value not in codes(db, kind):
        raise field_errors([((loc,), f"Pick one of your {what}. Change them in Settings -> Lists.")])


def not_found(what: str = "record") -> HTTPException:
    # Same answer whether it doesn't exist or belongs to a team you can't see.
    return HTTPException(status.HTTP_404_NOT_FOUND, f"That {what} doesn't exist, or it's in a team you can't see.")


@dataclass
class Workspace:
    """Every sales division this person sells in, as one workspace.

    A division is not a place you go: Customers, Follow-ups and Retention are
    the same pages whichever division a record is in, so they are one list and
    a record carries its own division. Everything here therefore works over a
    set of scopes that may span divisions, and anything needing to know *which*
    division reads it off the record rather than off the address.

    A person in one division sees exactly what they always did — their set of
    scopes simply has one division in it.
    """

    divisions: tuple[str, ...]
    user: Profile
    access: Access
    db: Session
    records: Records
    settings: Settings

    def scopes(self, action: str) -> frozenset[Scope]:
        # Records of a division this workspace doesn't cover never belong in it,
        # whatever the grant says.
        return frozenset(
            scope
            for division in self.divisions
            for scope in self.access.scopes(division, action)
            if scope.division == division
        )

    def scope_of(self, division: str, team: str) -> Scope:
        """A scope named by a client. Refused unless it is one of this
        workspace's divisions, so no one can reach another by asking."""
        if division not in self.divisions or not is_code(division) or not is_code(team):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That isn't a team.")
        return Scope(division, team)

    def visible(self, division: str | None = None, team: str | None = None) -> frozenset[Scope]:
        """What this person may read. Narrowed to one team when the screen asks
        for one, which can only ever remove scopes, never add them."""
        scopes = self.scopes("view")
        if not scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this workspace.")
        if team:
            if not division:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Say which division that team is in.")
            scopes = scopes & {self.scope_of(division, team)}
        elif division:
            scopes = frozenset(s for s in scopes if s.division == division)
        return scopes

    def can(self, action: str, scope: Scope) -> bool:
        return self.access.can_in(scope.division, action, scope)

    def require(self, action: str, scope: Scope) -> None:
        self.access.require(scope.division, action, scope)

    @cached_property
    def division_names(self) -> dict[str, str]:
        """What this company calls each of them — it may have renamed one, or
        added it in the first place."""
        rows = self.db.execute(select(Division.code, Division.name).where(Division.code.in_(self.divisions)))
        return dict(rows.all())

    @cached_property
    def team_names(self) -> dict[tuple[str, str], str]:
        rows = self.db.execute(
            select(Subdivision.division_code, Subdivision.code, Subdivision.name).where(
                Subdivision.division_code.in_(self.divisions)
            )
        )
        return {(division, code): name for division, code, name in rows.all()}

    @cached_property
    def hq_names(self) -> dict[tuple[str, str, str], str]:
        rows = self.db.execute(
            select(
                Headquarters.division_code, Headquarters.subdivision_code, Headquarters.code, Headquarters.name
            ).where(Headquarters.division_code.in_(self.divisions))
        )
        return {(division, team, code): name for division, team, code, name in rows.all()}

    def division_name(self, scope: Scope) -> str:
        return self.division_names.get(scope.division, scope.division)

    def team_name(self, scope: Scope) -> str:
        return self.team_names.get((scope.division, scope.subdivision), scope.subdivision)

    def hq_name(self, scope: Scope, code: str | None) -> str | None:
        return self.hq_names.get((scope.division, scope.subdivision, code)) if code else None

    def active_team(self, division: str, team: str) -> Scope:
        scope = self.scope_of(division, team)
        row = org_get(self.db, Subdivision, division, team)
        if row is None or not row.is_active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick one of this division's active teams.")
        return scope

    def check_headquarters(self, scope: Scope, code: str | None) -> None:
        if code is None:
            return
        hq = org_get(self.db, Headquarters, scope.division, scope.subdivision, code)
        if hq is None or not hq.is_active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That headquarters isn't under this team.")

    def check_assignee(self, scope: Scope, user_id: str) -> Profile:
        everyone = access_for_everyone(self.db)
        entry = everyone.get(user_id)
        if entry is None or not entry[1].can_in(scope.division, "view", scope):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That person can't see this team's records.")
        return entry[0]

    def customer(self, customer_id: str) -> dict:
        doc = self.records.get(CUSTOMER, customer_id, self.visible())
        if doc is None:
            raise not_found("customer")
        return doc

    def children(self, customer_id: str, scope: Scope) -> list[dict]:
        found: list[dict] = []
        for doc_type in CHILD_TYPES:
            offset = 0
            while True:
                page = self.records.find(
                    Query(doc_type, {scope}, (Eq("customerId", customer_id),), (("_id", "asc"),), offset, MAX_LIMIT)
                )
                found += page
                if len(page) < MAX_LIMIT:
                    break
                offset += MAX_LIMIT
        return found

    def customer_names(self, docs: list[dict]) -> dict[str, str]:
        ids = tuple({d["customerId"] for d in docs if d.get("customerId")})
        if not ids:
            return {}
        hits = self.records.find(Query(CUSTOMER, self.visible(), (In("_id", ids),), limit=len(ids)))
        return {h["_id"]: h["name"] for h in hits}


def get_workspace(
    user: CurrentUser,
    access: CurrentAccess,
    db: DB,
    records: RecordsDep,
    settings: SettingsDep,
) -> Workspace:
    """The sales divisions this person actually sells in, in the company's own
    order. A company's own divisions count, not only the six Orbit ships with
    (app/catalogue.py)."""
    divisions = tuple(key for key in sales_keys(db) if access.scopes(key, "view"))
    return Workspace(divisions, user, access, db, records, settings)


WS = Annotated[Workspace, Depends(get_workspace)]


# --- shaping -------------------------------------------------------------------


def customer_out(ws: Workspace, doc: dict) -> dict:
    scope = Scope.of(doc)
    hq = doc.get("headquarters")
    return {
        "id": doc["_id"],
        "rev": doc.get("_rev"),
        "division": scope.division,
        "divisionName": ws.division_name(scope),
        "team": scope.subdivision,
        "teamName": ws.team_name(scope),
        "headquarters": hq,
        "headquartersName": ws.hq_name(scope, hq),
        "name": doc["name"],
        "kind": doc["kind"],
        "status": doc["status"],
        **{f: doc.get(f) for f in CUSTOMER_TEXT_FIELDS},
        "details": doc.get("details") or {},
        "owner": {"id": doc.get("ownerId"), "name": doc.get("ownerName")},
        "lastContactAt": doc.get("lastContactAt"),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
        "can": {
            "edit": ws.can("edit", scope),
            "delete": ws.can("delete", scope),
            "log": ws.can("create", scope),
        },
    }


def activity_out(ws: Workspace, doc: dict, names: dict[str, str] | None = None) -> dict:
    scope = Scope.of(doc)
    return {
        "id": doc["_id"],
        "customerId": doc["customerId"],
        "customerName": (names or {}).get(doc["customerId"]),
        "division": scope.division,
        "divisionName": ws.division_name(scope),
        "team": scope.subdivision,
        "teamName": ws.team_name(scope),
        "kind": doc["kind"],
        "outcome": doc.get("outcome"),
        "summary": doc["summary"],
        "occurredAt": doc["occurredAt"],
        "by": {"id": doc.get("byId"), "name": doc.get("byName")},
        "can": {"delete": ws.can("delete", scope)},
    }


def follow_up_out(ws: Workspace, doc: dict, day: str, names: dict[str, str] | None = None) -> dict:
    scope = Scope.of(doc)
    due = doc["dueOn"]
    bucket = None
    if doc["status"] == "open":
        bucket = "overdue" if due < day else "today" if due == day else "upcoming"
    return {
        "id": doc["_id"],
        "rev": doc.get("_rev"),
        "customerId": doc["customerId"],
        "customerName": (names or {}).get(doc["customerId"]),
        "division": scope.division,
        "divisionName": ws.division_name(scope),
        "team": scope.subdivision,
        "teamName": ws.team_name(scope),
        "title": doc["title"],
        "dueOn": due,
        "bucket": bucket,
        "status": doc["status"],
        "assignee": {"id": doc.get("assigneeId"), "name": doc.get("assigneeName")},
        "doneAt": doc.get("doneAt"),
        "doneBy": {"id": doc.get("doneById"), "name": doc.get("doneByName")} if doc.get("doneById") else None,
        "can": {"edit": ws.can("edit", scope)},
    }


def follow_up_doc(
    ws: Workspace, scope: Scope, customer_id: str, body: FollowUpIn, assignee: Profile | None = None
) -> dict:
    """`assignee` when it's already been checked against the scope (bulk actions do it once per batch)."""
    if assignee is None:
        assignee = ws.check_assignee(scope, body.assignee_id) if body.assignee_id else ws.user
    return {
        "_id": new_id(),
        "_type": FOLLOW_UP,
        **scope.stamp(),
        "customerId": customer_id,
        "title": body.title,
        "dueOn": body.due_on.isoformat(),
        "status": "open",
        "assigneeId": assignee.id,
        "assigneeName": assignee.full_name,
        "createdAt": now_iso(),
        "createdById": ws.user.id,
    }


def find_duplicates(records: Records, scopes: frozenset[Scope], name: str, phone: str | None) -> list[dict]:
    """Customers with this name or phone number, among `scopes` only: looking
    further would reveal records in teams the person has no access to."""
    checks = [Query(CUSTOMER, scopes, (Eq("sortName", name.casefold()),), limit=5)]
    digits = phone_digits(phone)
    if digits and len(digits) >= 7:
        checks.append(Query(CUSTOMER, scopes, (Eq("phoneDigits", digits),), limit=5))
    found: dict[str, dict] = {}
    for q in checks:
        for doc in records.find(q):
            found[doc["_id"]] = doc
    return list(found.values())


def duplicates(ws: Workspace, name: str, phone: str | None) -> list[dict]:
    """Possible duplicates among the customers this person can see."""
    return [
        {
            "id": d["_id"],
            "name": d["name"],
            "divisionName": ws.division_name(Scope.of(d)),
            "teamName": ws.team_name(Scope.of(d)),
            "phone": d.get("phone"),
        }
        for d in find_duplicates(ws.records, ws.visible(), name, phone)
    ]


# --- overview --------------------------------------------------------------------


@router.get("/summary")
def summary(ws: WS, division: str | None = None, team: str | None = None) -> dict:
    """The overview, across every division this person sells in. `division`
    narrows it for anyone who wants one division's figures on their own."""
    scopes = ws.visible(division, team)
    day = today(ws.settings)
    mine = (Eq("assigneeId", ws.user.id), Eq("status", "open"))
    due = ws.records.find(
        Query(FOLLOW_UP, scopes, (*mine, Cmp("dueOn", "<=", day)), order=(("dueOn", "asc"),), limit=8)
    )
    recent = ws.records.find(Query(ACTIVITY, scopes, order=(("occurredAt", "desc"),), limit=8))
    names = ws.customer_names(due + recent)
    return {
        "today": day,
        "counts": {
            "customers": ws.records.count(Query(CUSTOMER, scopes)),
            "leads": ws.records.count(Query(CUSTOMER, scopes, (Eq("status", "lead"),))),
            "overdue": ws.records.count(Query(FOLLOW_UP, scopes, (*mine, Cmp("dueOn", "<", day)))),
            "dueToday": ws.records.count(Query(FOLLOW_UP, scopes, (*mine, Eq("dueOn", day)))),
            "upcoming": ws.records.count(Query(FOLLOW_UP, scopes, (*mine, Cmp("dueOn", ">", day)))),
        },
        "dueFollowUps": [follow_up_out(ws, d, day, names) for d in due],
        "recentActivity": [activity_out(ws, d, names) for d in recent],
    }


@router.get("/people")
def people(ws: WS, division: str, team: str) -> list[dict]:
    """Who can be given a follow-up in this team: everyone who can see it."""
    scope = ws.scope_of(division, team)
    ws.require("view", scope)
    return sorted(
        (
            {"id": p.id, "name": p.full_name}
            for p, access in access_for_everyone(ws.db).values()
            if access.can_in(scope.division, "view", scope)
        ),
        key=lambda p: p["name"].casefold(),
    )


# --- customers -------------------------------------------------------------------


@router.get("/customers")
def list_customers(
    ws: WS,
    q: Annotated[str | None, Param(max_length=80)] = None,
    # One list across every division this person sells in. `division` and
    # `team` only ever narrow it, and only to something already theirs.
    division: str | None = None,
    team: str | None = None,
    status_: Annotated[Literal["lead", "active", "inactive"] | None, Param(alias="status")] = None,
    kind: str | None = None,
    offset: Annotated[int, Param(ge=0)] = 0,
    limit: Annotated[int, Param(ge=1, le=100)] = 25,
) -> dict:
    where = []
    if status_:
        where.append(Eq("status", status_))
    if kind:
        where.append(Eq("kind", kind))
    if q and q.strip():
        where.append(Search(("name", "city", "specialty", "phoneDigits"), q))
    scopes = ws.visible(division, team)
    items = ws.records.find(Query(CUSTOMER, scopes, tuple(where), (("sortName", "asc"),), offset, limit))
    return {
        "items": [customer_out(ws, d) for d in items],
        "total": ws.records.count(Query(CUSTOMER, scopes, tuple(where))),
    }


def customer_doc(user: Profile, scope: Scope, body: CustomerIn, details: dict | None = None) -> dict:
    """A new customer record, owned by whoever adds it.

    `details` holds this company's own customer fields, already checked against
    them. The Orders app raises customers too and doesn't ask for them yet, so
    it leaves them out rather than writing values nobody has checked."""
    stamp = now_iso()
    doc = {
        "_id": new_id(),
        "_type": CUSTOMER,
        **scope.stamp(),
        "headquarters": body.headquarters,
        "name": body.name,
        "sortName": body.name.casefold(),
        "kind": body.kind,
        "status": body.status,
        **{f: getattr(body, f) for f in CUSTOMER_TEXT_FIELDS},
        "details": details or None,
        "phoneDigits": phone_digits(body.phone),
        "ownerId": user.id,
        "ownerName": user.full_name,
        "createdAt": stamp,
        "createdById": user.id,
        "updatedAt": stamp,
    }
    return {k: v for k, v in doc.items() if v is not None}


@router.post("/customers", status_code=status.HTTP_201_CREATED)
def create_customer(ws: WS, body: CustomerIn) -> dict:
    scope = ws.active_team(body.division, body.team)
    ws.require("create", scope)
    ws.check_headquarters(scope, body.headquarters)
    if not body.allow_duplicate:
        matches = duplicates(ws, body.name, body.phone)
        if matches:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"message": "This looks like a customer you already have.", "duplicates": matches},
            )

    a_choice(ws.db, "customer_kind", body.kind, "kind", "customer kinds")
    doc = customer_doc(ws.user, scope, body, check_values(ws.db, "customer", body.details or {}))
    ws.records.commit([Create(doc)])
    audit(ws.db, ws.user, "customer.created", f"{doc['_id']} in {scope.key}")
    return customer_out(ws, ws.customer(doc["_id"]))


@router.get("/customers/{customer_id}")
def get_customer(ws: WS, customer_id: str) -> dict:
    doc = ws.customer(customer_id)
    scope = Scope.of(doc)
    day = today(ws.settings)
    activities = ws.records.find(
        Query(ACTIVITY, {scope}, (Eq("customerId", customer_id),), (("occurredAt", "desc"),), limit=100)
    )
    follow_ups = ws.records.find(
        Query(FOLLOW_UP, {scope}, (Eq("customerId", customer_id),), (("status", "desc"), ("dueOn", "asc")), limit=100)
    )
    quotes = ws.records.find(
        Query(QUOTE, {scope}, (Eq("customerId", customer_id),), (("createdAt", "desc"),), limit=100)
    )
    return {
        **customer_out(ws, doc),
        "activities": [activity_out(ws, a) for a in activities],
        "followUps": [follow_up_out(ws, f, day) for f in follow_ups],
        "quotes": [ws_quote_out(ws, q, doc["name"]) for q in quotes],
    }


@router.patch("/customers/{customer_id}")
def update_customer(ws: WS, customer_id: str, body: CustomerPatch) -> dict:
    doc = ws.customer(customer_id)
    old = Scope.of(doc)
    ws.require("edit", old)

    changes = body.model_dump(exclude_unset=True)
    if changes.pop("rev", None) not in (None, doc["_rev"]):
        raise ConflictError("edited from a stale copy")
    a_choice(ws.db, "customer_kind", changes.get("kind"), "kind", "customer kinds")
    if changes.get("details") is not None:
        changes["details"] = check_values(ws.db, "customer", changes["details"])
    new = old
    if "team" in changes and changes["team"] != old.subdivision:
        # A customer moves between teams, never between divisions: its quotes,
        # prices and retention window all belong to the division it is in.
        new = ws.active_team(old.division, changes["team"])
        ws.require("edit", new)
        if "headquarters" not in changes:
            changes["headquarters"] = None  # headquarters belong to the old team
    changes.pop("team", None)
    if changes.get("headquarters"):
        ws.check_headquarters(new, changes["headquarters"])

    # Duplicates are only checked on create; an edit is deliberate.
    if "name" in changes:
        changes["sortName"] = changes["name"].casefold()
    if "phone" in changes:
        changes["phoneDigits"] = phone_digits(changes["phone"])

    to_set = {k: v for k, v in changes.items() if v is not None}
    to_unset = tuple(k for k, v in changes.items() if v is None)
    to_set["updatedAt"] = now_iso()

    mutations: list = []
    if new != old:
        to_set.update(new.stamp())
        mutations += [Patch(child["_id"], new.stamp()) for child in ws.children(customer_id, old)]
    # Pinned to the revision this request read: if anything was logged against
    # the customer meanwhile, its children list is stale and the move is refused.
    mutations.insert(0, Patch(customer_id, to_set, to_unset, if_revision=doc["_rev"]))
    ws.records.commit(mutations)
    moved = f": {old.key} -> {new.key}" if new != old else ""
    audit(ws.db, ws.user, "customer.moved" if moved else "customer.updated", customer_id + moved, changes)
    return customer_out(ws, ws.customer(customer_id))


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(ws: WS, files: FilesDep, customer_id: str) -> None:
    doc = ws.customer(customer_id)
    scope = Scope.of(doc)
    ws.require("delete", scope)
    children = ws.children(customer_id, scope)
    # The patch fails the whole transaction if the customer changed since it was read.
    guard = Patch(customer_id, {"updatedAt": now_iso()}, if_revision=doc["_rev"])
    ws.records.commit([guard, *(Delete(c["_id"]) for c in children), Delete(customer_id)])
    for child in children:
        if ref := letter_file_ref(child):
            files.delete(ref)
    audit(ws.db, ws.user, "customer.deleted", f"{customer_id} and {len(children)} linked records in {scope.key}")


# --- activities ------------------------------------------------------------------


@router.post("/customers/{customer_id}/activities", status_code=status.HTTP_201_CREATED)
def log_activity(ws: WS, customer_id: str, body: ActivityIn) -> dict:
    customer = ws.customer(customer_id)
    scope = Scope.of(customer)
    ws.require("create", scope)

    a_choice(ws.db, "activity_kind", body.kind, "kind", "activity kinds")
    a_choice(ws.db, "outcome", body.outcome, "outcome", "call outcomes")
    occurred = (body.occurred_at or datetime.now(UTC)).astimezone(UTC)
    occurred_iso = occurred.isoformat(timespec="seconds").replace("+00:00", "Z")
    activity = {
        "_id": new_id(),
        "_type": ACTIVITY,
        **scope.stamp(),
        "customerId": customer_id,
        "kind": body.kind,
        "summary": body.summary,
        "occurredAt": occurred_iso,
        "byId": ws.user.id,
        "byName": ws.user.full_name,
        "createdAt": now_iso(),
    }
    if body.outcome:
        activity["outcome"] = body.outcome

    mutations: list = [Create(activity)]
    if body.follow_up:
        mutations.append(Create(follow_up_doc(ws, scope, customer_id, body.follow_up)))
    # Touching the customer at the revision read ties this activity to its current
    # team: a move committed in between makes this fail instead of leaving it behind.
    last = max(occurred_iso, customer.get("lastContactAt", ""))
    mutations.append(Patch(customer_id, {"lastContactAt": last}, if_revision=customer["_rev"]))
    ws.records.commit(mutations)
    return activity_out(ws, activity, {customer_id: customer["name"]})


@router.delete("/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(ws: WS, activity_id: str) -> None:
    doc = ws.records.get(ACTIVITY, activity_id, ws.visible())
    if doc is None:
        raise not_found("activity")
    ws.require("delete", Scope.of(doc))
    ws.records.commit([Delete(activity_id)])


# --- follow-ups ------------------------------------------------------------------


@router.get("/follow-ups")
def list_follow_ups(
    ws: WS,
    state: Literal["open", "done"] = "open",
    who: Literal["me", "team"] = "me",
    division: str | None = None,
    team: str | None = None,
) -> dict:
    scopes = ws.visible(division, team)
    day = today(ws.settings)
    where: list = [Eq("status", state)]
    if who == "me":
        where.append(Eq("assigneeId", ws.user.id))
    order = (("dueOn", "asc"),) if state == "open" else (("doneAt", "desc"),)
    docs = ws.records.find(Query(FOLLOW_UP, scopes, tuple(where), order, limit=200 if state == "open" else 50))
    names = ws.customer_names(docs)
    return {"today": day, "items": [follow_up_out(ws, d, day, names) for d in docs]}


@router.post("/customers/{customer_id}/follow-ups", status_code=status.HTTP_201_CREATED)
def add_follow_up(ws: WS, customer_id: str, body: FollowUpIn) -> dict:
    customer = ws.customer(customer_id)
    scope = Scope.of(customer)
    ws.require("create", scope)
    doc = follow_up_doc(ws, scope, customer_id, body)
    ws.records.commit([Create(doc), Patch(customer_id, {"updatedAt": now_iso()}, if_revision=customer["_rev"])])
    return follow_up_out(ws, doc, today(ws.settings), {customer_id: customer["name"]})


@router.patch("/follow-ups/{follow_up_id}")
def update_follow_up(ws: WS, follow_up_id: str, body: FollowUpPatch) -> dict:
    doc = ws.records.get(FOLLOW_UP, follow_up_id, ws.visible())
    if doc is None:
        raise not_found("follow-up")
    scope = Scope.of(doc)
    ws.require("edit", scope)

    to_set: dict = {}
    to_unset: tuple[str, ...] = ()
    if body.title is not None:
        to_set["title"] = body.title
    if body.due_on is not None:
        to_set["dueOn"] = body.due_on.isoformat()
    if body.assignee_id is not None:
        person = ws.check_assignee(scope, body.assignee_id)
        to_set |= {"assigneeId": person.id, "assigneeName": person.full_name}
    if body.status == "done" and doc["status"] != "done":
        to_set |= {"status": "done", "doneAt": now_iso(), "doneById": ws.user.id, "doneByName": ws.user.full_name}
    elif body.status == "open" and doc["status"] != "open":
        to_set["status"] = "open"
        to_unset = ("doneAt", "doneById", "doneByName")
    if to_set or to_unset:
        ws.records.commit([Patch(follow_up_id, to_set, to_unset)])
    updated = ws.records.get(FOLLOW_UP, follow_up_id, {scope})
    names = ws.customer_names([updated])
    return follow_up_out(ws, updated, today(ws.settings), names)


# --- quotes --------------------------------------------------------------------------


def ws_quote_out(ws: Workspace, doc: dict, customer_name: str | None = None) -> dict:
    scope = Scope.of(doc)
    return quote_out(
        doc,
        division_name=ws.division_name(scope),
        team_name=ws.team_name(scope),
        customer_name=customer_name,
        can={
            "delete": ws.can("delete", scope) and not finance_has_acted(doc),
            # Raising the order is an Orders grant, not a sales one, and a quote
            # Finance hasn't finished with isn't ready to become one.
            "order": ws.access.can_in(ORDERS, "raise", scope) and state(doc) == "ready",
        },
    )


def price_in(
    db: Session, division: str, day: date, body: QuoteIn, paperwork: bool = True, team: str | None = None
) -> PricedQuote:
    """Prices lines with a division's rules, on a day's promos. Raises PricingError.
    Quotes here and orders in the Orders app are both priced by this.

    With a team, its own prices stand over the company's wherever its lead set
    one, and its own choice of price types applies."""
    bundles = load_bundles(db, division, day)
    # A bundle line names no product, so the products it contains have to be
    # loaded too — including for a bundle the rep can't actually use, whose
    # refusal the pricing engine words.
    ids = {line.product_id for line in body.lines if line.product_id}
    for line in body.lines:
        bundle = bundles.get(line.bundle_id) if line.bundle_id else None
        if bundle:
            ids |= {item.product_id for item in bundle.items}
    return price_quote(
        body,
        load_rules(db, division, team),
        load_price_types(db),
        load_products(db, ids, division=division, team=team),
        load_promos(db, division, day),
        load_issuers(db),
        paperwork=paperwork,
        bundles=bundles,
    )


def price(ws: Workspace, scope: Scope, body: QuoteIn, paperwork: bool = True) -> PricedQuote:
    """Prices a quote with the customer's division's rules, and its team's own prices."""
    return price_in(ws.db, scope.division, today_date(ws.settings), body, paperwork, scope.subdivision)


@router.get("/customers/{customer_id}/price-list")
def price_list(ws: WS, customer_id: str) -> dict:
    """What may be quoted to this customer.

    Taken from the customer rather than asked for, because a customer belongs
    to one division and one team: there is no second answer to get wrong, and a
    rep can't price against a division they merely happen to sell in too."""
    scope = Scope.of(ws.customer(customer_id))
    return price_list_for(ws.db, scope.division, today_date(ws.settings), scope.subdivision)


def price_list_for(db: Session, division: str, day: date, team: str | None = None) -> dict:
    """What may be quoted in a division: only its price types, and only those
    prices of each product, so B2C never sees a Distributor's Price. With a
    team, its own prices and its own choice of price types."""
    rules = load_rules(db, division, team)
    types = [t for t in load_price_types(db).values() if t.code in rules.price_types]
    list_codes = {t.code for t in types if t.entry == "list"}
    products = db.scalars(
        select(Product).where(Product.is_active.is_(True)).options(selectinload(Product.prices)).order_by(Product.name)
    )
    # The team's own prices stand over the company's, exactly as they do when
    # the quote is priced, so the rep reads the number they will be charged.
    theirs = load_team_prices(db, division, team) if team else {}
    issuers = load_issuers(db) if rules.allows_guarantee_letters else {}
    promos = load_promos(db, division, day)
    return {
        "usesPriceList": rules.uses_price_list,
        "allowsGuaranteeLetters": rules.allows_guarantee_letters,
        "discountApprovalBp": rules.discount_approval_bp,
        "priceTypes": [
            {
                "code": t.code,
                "name": t.name,
                "entry": t.entry,
                "rule": rules.price_types[t.code],
                "requiresNotes": t.requires_notes,
                "needsApproval": t.needs_approval,
            }
            for t in types
        ],
        "issuers": [{"code": code, "name": name} for code, name in issuers.items()],
        "products": [
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "genericName": p.generic_name,
                "strength": p.strength,
                "form": p.form,
                "unit": p.unit,
                "prices": {
                    code: amount
                    for code, amount in (
                        {x.price_type_code: x.amount_centavos for x in p.prices}
                        | {ptype: amount for (pid, ptype), amount in theirs.items() if pid == p.id}
                    ).items()
                    if code in list_codes
                },
            }
            for p in products
        ],
        "promos": [
            {
                "id": p.id,
                "name": p.name,
                "kind": p.kind,
                "percentBp": p.percent_bp,
                "amountCentavos": p.amount_centavos,
                "buyQty": p.buy_qty,
                "freeQty": p.free_qty,
                "tiers": [{"minQty": q, "percentBp": bp} for q, bp in p.tiers],
                "productIds": sorted(p.product_ids) if p.product_ids is not None else None,
            }
            for p in promos.values()
        ],
        # Picked instead of a product, not on top of one, so the form lists
        # these beside the products rather than beside the promos.
        "bundles": [
            {
                "id": b.id,
                "code": b.code,
                "name": b.name,
                "priceCentavos": b.price_centavos,
                "asOneLine": b.as_one_line,
                "items": [{"productId": i.product_id, "qty": i.qty} for i in b.items],
            }
            for b in load_bundles(db, division, day).values()
        ],
    }


@router.post("/customers/{customer_id}/quotes/preview")
def preview_quote(ws: WS, customer_id: str, body: QuoteIn) -> dict:
    """Totals for the form as the rep fills it in. The server prices; the browser only shows."""
    scope = Scope.of(ws.customer(customer_id))
    try:
        return priced_out(price(ws, scope, body, paperwork=False))
    except PricingError as exc:
        raise field_errors(exc.errors) from exc


@router.post("/customers/{customer_id}/quotes", status_code=status.HTTP_201_CREATED)
def create_quote(
    ws: WS,
    files: FilesDep,
    customer_id: str,
    quote: Annotated[str, Form(max_length=200_000)],
    letter_file: Annotated[UploadFile | None, File(alias="letterFile")] = None,
) -> dict:
    """Multipart: the quote as JSON in `quote`, and the guarantee letter's file
    in `letterFile` when a DSWD, PCSO... pays."""
    customer = ws.customer(customer_id)
    scope = Scope.of(customer)
    ws.require("create", scope)
    try:
        body = QuoteIn.model_validate_json(quote)
    except ValidationError as exc:
        raise field_errors([(tuple(e["loc"]), e["msg"]) for e in exc.errors()]) from exc

    errors: list = []
    priced = None
    try:
        priced = price(ws, scope, body)
    except PricingError as exc:
        errors += exc.errors

    data, kind = None, None
    if body.payer != SELF:
        if letter_file is None:
            errors.append((("letterFile",), "Attach the guarantee letter: a PDF, or a photo (JPG or PNG)."))
        else:
            data = letter_file.file.read(MAX_LETTER_BYTES + 1)
            kind = sniff(data)
            if len(data) > MAX_LETTER_BYTES:
                errors.append((("letterFile",), "The letter file is over 8 MB. Scan it at a lower resolution."))
            elif kind is None:
                errors.append((("letterFile",), "Attach a PDF, JPG or PNG file."))
    if errors or priced is None:
        raise field_errors(errors)

    ref = files.put(data) if data is not None and kind else None
    letter_meta = None
    if ref and kind:
        name = (letter_file.filename or f"letter.{kind[1]}")[-120:] if letter_file else f"letter.{kind[1]}"
        letter_meta = {"ref": ref, "name": name, "contentType": kind[0], "ext": kind[1], "size": len(data or b"")}
    doc = quote_doc(
        quote_id=new_id(),
        scope=scope,
        customer=customer,
        quote=body,
        priced=priced,
        payer_name=load_issuers(ws.db).get(body.payer),
        letter_file=letter_meta,
        user=ws.user,
        now=now_iso(),
    )
    try:
        # Touching the customer at the revision read ties the quote to its current team.
        ws.records.commit([Create(doc), Patch(customer_id, {"updatedAt": now_iso()}, if_revision=customer["_rev"])])
    except Exception:
        if ref:
            files.delete(ref)
        raise
    audit(ws.db, ws.user, "quote.created", f"{doc['number']} for {customer_id} in {scope.key}")
    return ws_quote_out(ws, ws.records.get(QUOTE, doc["_id"], {scope}) or doc, customer["name"])


def visible_quote(ws: Workspace, quote_id: str) -> dict:
    doc = ws.records.get(QUOTE, quote_id, ws.visible())
    if doc is None:
        raise not_found("quote")
    return doc


@router.get("/quotes/{quote_id}")
def get_quote(ws: WS, quote_id: str) -> dict:
    doc = visible_quote(ws, quote_id)
    return ws_quote_out(ws, doc, ws.customer_names([doc]).get(doc["customerId"]))


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quote(ws: WS, files: FilesDep, quote_id: str) -> None:
    doc = visible_quote(ws, quote_id)
    ws.require("delete", Scope.of(doc))
    if finance_has_acted(doc):
        raise HTTPException(status.HTTP_409_CONFLICT, "Finance has already acted on this quote, so it stays on record.")
    ws.records.commit([Patch(quote_id, {"deletedAt": now_iso()}, if_revision=doc["_rev"]), Delete(quote_id)])
    if ref := letter_file_ref(doc):
        files.delete(ref)
    audit(ws.db, ws.user, "quote.deleted", doc["number"])


@router.get("/quotes/{quote_id}/letter")
def quote_letter(ws: WS, files: FilesDep, quote_id: str) -> Response:
    return letter_response(visible_quote(ws, quote_id), files)
