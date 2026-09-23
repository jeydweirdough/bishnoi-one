"""The Orders app's API: everything it needs from Orbit, so each rule lives in one place.

The Orders app keeps its own order tables. For who may do what, customers,
products, prices and the order settings it asks here, with the signed-in
person's own token (handed over at sign-in, see sso.py), so Orbit applies that
person's divisions and teams to every answer. The rule for customers and
prices: you see them where you may raise or edit orders.

The order settings can also be read with an API key (X-Api-Key) that has the
"orders:config" scope, for the Orders app's scheduled jobs.
"""

import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query as Param, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access, active_member, load_access
from app.audit import audit
from app.deps import DB, CurrentAccess, CurrentClaims, CurrentOrg, CurrentUser, RecordsDep, SettingsDep, current_claims, current_user
from app.errors import field_errors
from app.models import ApiKey, Division, Headquarters, Organization, SessionRecord, Subdivision, utcnow
from app.modules import ORDER_ACTIONS, ORDERS
from app.order_settings import settings_out
from app.pricing import PricingError
from app.quotes import QUOTE, priced_out, state
from app.routers.sales import CUSTOMER, CUSTOMER_TEXT_FIELDS, customer_doc, find_duplicates, price_in, price_list_for, today_date
from app.routers.sso import digest
from app.schemas import OrdersCustomerIn, QuoteIn
from app.scope import Scope
from app.store.query import Eq, Query, Search
from app.store.records import Create
from app.tenancy import all_companies, org_get, set_company

router = APIRouter(prefix="/orders-api/v1", tags=["orders app"])

CONFIG_SCOPE = "orders:config"


def order_access(access: CurrentAccess) -> Access:
    if not any(access.can(ORDERS, a) for a in ORDER_ACTIONS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't work on orders.")
    return access


OrderAccess = Annotated[Access, Depends(order_access)]


def raising(access: Access) -> frozenset[Scope]:
    """Where the person may raise or edit orders: where customers and prices are theirs to use."""
    return access.scopes(ORDERS, "raise") | access.scopes(ORDERS, "edit")


def in_division(scopes: frozenset[Scope], division: str) -> frozenset[Scope]:
    return frozenset(s for s in scopes if s.division == division)


def customer_brief(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "name": doc["name"],
        "kind": doc["kind"],
        "status": doc["status"],
        "division": doc["division"],
        "team": doc["subdivision"],
        "headquarters": doc.get("headquarters"),
        **{f: doc.get(f) for f in CUSTOMER_TEXT_FIELDS if f != "notes"},
    }


# --- who's asking ----------------------------------------------------------------------


@router.get("/me")
def me(user: CurrentUser, org: CurrentOrg, access: OrderAccess, claims: CurrentClaims, db: DB) -> dict:
    grants = {
        action: sorted(({"division": s.division, "team": s.subdivision} for s in access.scopes(ORDERS, action)), key=lambda g: (g["division"], g["team"]))
        for action in ORDER_ACTIONS
        if access.can(ORDERS, action)
    }
    reached = {(g["division"], g["team"]) for scopes in grants.values() for g in scopes}
    divisions = {d.code: d for d in db.scalars(select(Division).where(Division.code.in_({d for d, _ in reached})))}
    teams = db.scalars(select(Subdivision).where(Subdivision.division_code.in_(divisions)).order_by(Subdivision.sort_order))
    hqs = db.scalars(select(Headquarters).where(Headquarters.division_code.in_(divisions)).order_by(Headquarters.name))
    hq_by_team: dict[tuple[str, str], list[dict]] = {}
    for h in hqs:
        hq_by_team.setdefault((h.division_code, h.subdivision_code), []).append({"code": h.code, "name": h.name, "isActive": h.is_active})
    tree: dict[str, dict] = {}
    for t in teams:
        if (t.division_code, t.code) not in reached:
            continue
        d = divisions[t.division_code]
        entry = tree.setdefault(d.code, {"code": d.code, "name": d.name, "sortOrder": d.sort_order, "teams": []})
        entry["teams"].append(
            {"code": t.code, "name": t.name, "isActive": t.is_active, "headquarters": hq_by_team.get((d.code, t.code), [])}
        )
    session = db.get(SessionRecord, claims.session_id)
    membership = active_member(db, user.id)
    return {
        "user": {"id": user.id, "email": user.email, "fullName": user.full_name},
        "org": {
            "id": org.id,
            "slug": org.slug,
            "name": org.name,
            "brandName": org.brand_name,
            "currency": org.currency,
            "minorUnits": org.minor_units,
            "locale": org.locale,
            "timezone": org.timezone,
            "orderPrefix": org.order_prefix,
        },
        "grants": grants,
        "divisions": [
            {k: v for k, v in d.items() if k != "sortOrder"} for d in sorted(tree.values(), key=lambda d: d["sortOrder"])
        ],
        # Their manager in HR (once HR is connected): a team lead only endorses their own people's orders.
        "managerId": membership.manager_id if membership else None,
        "sessionExpiresAt": session.expires_at.isoformat() if session else None,
    }


# --- customers -------------------------------------------------------------------------


@router.get("/customers")
def customers(
    access: OrderAccess,
    records: RecordsDep,
    q: Annotated[str | None, Param(max_length=80)] = None,
    division: str | None = None,
    team: str | None = None,
    limit: Annotated[int, Param(ge=1, le=50)] = 20,
) -> dict:
    scopes = raising(access)
    if division:
        scopes = in_division(scopes, division)
    if team:
        scopes = frozenset(s for s in scopes if s.subdivision == team)
    where = (Search(("name", "city", "specialty", "phoneDigits"), q),) if q and q.strip() else ()
    items = records.find(Query(CUSTOMER, scopes, where, (("sortName", "asc"),), 0, limit))
    return {"items": [customer_brief(d) for d in items]}


@router.get("/customers/{customer_id}")
def customer(customer_id: str, access: OrderAccess, records: RecordsDep) -> dict:
    hits = records.find(Query(CUSTOMER, raising(access), (Eq("_id", customer_id),), limit=1))
    if not hits:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such customer, or it's in a team you don't raise orders for.")
    return customer_brief(hits[0])


@router.post("/customers", status_code=status.HTTP_201_CREATED)
def add_customer(body: OrdersCustomerIn, user: CurrentUser, access: OrderAccess, records: RecordsDep, db: DB) -> dict:
    """A customer added while raising an order, in a team the person raises orders for."""
    scope = Scope(body.division, body.team)
    if scope not in access.scopes(ORDERS, "raise"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't raise orders for that team.")
    team = org_get(db, Subdivision, body.division, body.team)
    if team is None or not team.is_active:
        raise field_errors([(("team",), "That team is switched off.")])
    if body.headquarters:
        hq = org_get(db, Headquarters, body.division, body.team, body.headquarters)
        if hq is None or not hq.is_active:
            raise field_errors([(("headquarters",), "Pick one of the team's headquarters.")])
    if not body.allow_duplicate:
        matches = find_duplicates(records, raising(access), body.name, body.phone)
        if matches:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"message": "This looks like a customer you already have.", "duplicates": [customer_brief(d) for d in matches]},
            )
    doc = customer_doc(user, scope, body)
    records.commit([Create(doc)])
    audit(db, user, "customer.created", f"{doc['_id']} in {scope.key} (from Orders)")
    return customer_brief(records.find(Query(CUSTOMER, {scope}, (Eq("_id", doc["_id"]),), limit=1))[0])


# --- products and prices ---------------------------------------------------------------


def division_for(access: Access, division: str, actions: tuple[str, ...]) -> str:
    if not any(s.division == division for a in actions for s in access.scopes(ORDERS, a)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't work on that division's orders.")
    return division


@router.get("/products")
def products(division: str, access: OrderAccess, db: DB, settings: SettingsDep, team: str | None = None) -> dict:
    """The division's price list: its price types, products with only those
    prices, and today's promos. With a team, that team's own prices."""
    return price_list_for(db, division_for(access, division, ORDER_ACTIONS), today_date(settings), team)


@router.post("/pricing/price")
def price(division: str, body: QuoteIn, access: OrderAccess, db: DB, settings: SettingsDep, team: str | None = None) -> dict:
    """Prices order lines with Orbit's own engine: the same totals a quote would
    get. An order raised in a team is priced with that team's own prices."""
    division_for(access, division, ("raise", "edit"))
    try:
        return priced_out(price_in(db, division, today_date(settings), body, paperwork=False, team=team))
    except PricingError as exc:
        raise field_errors(exc.errors) from exc


# --- order settings --------------------------------------------------------------------


def key_company(db: Session, raw: str, scope: str) -> ApiKey:
    """The API key's company is set on the session. Refused: 401, one answer for every reason."""
    refused = HTTPException(status.HTTP_401_UNAUTHORIZED, "That API key isn't valid.")
    try:
        prefix, key_id, secret = raw.split("_", 2)
    except ValueError:
        raise refused from None
    if prefix != "orbit":
        raise refused
    with all_companies(db):
        key = db.get(ApiKey, key_id)
        if key is None or key.revoked_at is not None or not hmac.compare_digest(key.secret_hash, digest(secret)):
            raise refused
        org = db.get(Organization, key.org_id)
        if org is None or org.status != "active":
            raise refused
        key.last_used_at = utcnow()
        db.commit()
    if scope not in (key.scopes or []):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That API key can't do this.")
    set_company(db, key.org_id)
    return key


@dataclass
class ConfigReader:
    db: Session


def config_reader(request: Request, db: DB, settings: SettingsDep) -> ConfigReader:
    """A person who works on orders, or an API key allowed to read the order settings."""
    raw = request.headers.get("x-api-key")
    if raw:
        key_company(db, raw, CONFIG_SCOPE)
        return ConfigReader(db)
    auth = request.headers.get("authorization", "")
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    user = current_user(request, current_claims(settings, bearer), db)
    order_access(load_access(db, user.id))
    return ConfigReader(db)


@router.get("/config")
def config(reader: Annotated[ConfigReader, Depends(config_reader)]) -> dict:
    """The order form's lists (switched-off items too, so old orders still name them), extra fields and rules."""
    return settings_out(reader.db)


# --- quotes -----------------------------------------------------------------------------
#
# A quote is a priced request a rep has already agreed with the customer, so an
# order raised from one should not be typed out again. The Orders app fetches it
# here to fill its form in.
#
# That is the whole of it. The Orders app keeps the quote's id on its order, so
# "which order came from this quote" is a question its own tables answer, and
# Orbit keeps no copy: an order's existence, its steps and its history are the
# Orders app's, and mirroring any of it here would be the same thing written
# twice, wrong the moment the two disagree. When Orbit shows orders it will read
# them (a read-only role on the orders tables), never keep its own.


def orderable(doc: dict) -> None:
    """Refuse a quote that has no business becoming an order yet.

    A rejected one must never become an order; one still waiting on Finance
    must wait, or the approval would mean nothing."""
    where = state(doc)
    if where == "rejected":
        raise HTTPException(status.HTTP_409_CONFLICT, "Finance rejected this quote, so it can't become an order.")
    if where == "waiting":
        raise HTTPException(status.HTTP_409_CONFLICT, "This quote is still waiting on Finance.")


def quote_for_order(doc: dict, customer: dict | None) -> dict:
    """A quote as the Orders app needs it: who it is for, what was agreed, and
    at what price. The lines are exactly as they were priced and saved, so an
    order raised today charges what the customer was quoted."""
    scope = Scope.of(doc)
    letter = doc.get("letter")
    return {
        "id": doc["_id"],
        "number": doc["number"],
        "division": scope.division,
        "team": scope.subdivision,
        "customerId": doc["customerId"],
        "customer": customer_brief(customer) if customer else None,
        "priceType": doc["priceType"],
        "priceTypeName": doc["priceTypeName"],
        "rx": doc.get("rx", False),
        "payer": doc["payer"],
        "payerName": doc.get("payerName"),
        "notes": doc.get("notes"),
        # The guarantee letter travels as its particulars only. Its file stays in
        # Orbit, where Finance verified it.
        "letter": (
            {"number": letter["number"], "issuedOn": letter["issuedOn"], "amountCentavos": letter["amountCentavos"]}
            if letter
            else None
        ),
        "lines": doc["lines"],
        "grossCentavos": doc["grossCentavos"],
        "promoDiscountCentavos": doc["promoDiscountCentavos"],
        "discountCentavos": doc["discountCentavos"],
        "totalCentavos": doc["totalCentavos"],
    }


@router.get("/quotes/{quote_id}")
def quote(quote_id: str, access: OrderAccess, records: RecordsDep) -> dict:
    """A quote to raise an order from.

    Only where this person may raise orders. Being able to read a quote in the
    sales workspace is not enough: raising the order is the thing being allowed
    here, and that is an Orders grant."""
    doc = records.get(QUOTE, quote_id, raising(access))
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such quote, or it isn't one you raise orders for.")
    orderable(doc)
    customer = records.get(CUSTOMER, doc["customerId"], raising(access))
    return quote_for_order(doc, customer)
