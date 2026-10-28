"""What other Bishnoi One apps may read from the CRM: its customers, for Finance to
invoice. Only for an app holding one of INTEGRATION_KEYS, sent in the
X-Bishnoi-Key header (the same way the CRM reads Inventory and asks Finance).

Read-only, and only what an invoice needs: who the customer is, where they
are, how to reach them, and their TIN when the company keeps one (an added
field named "tin" on the customer form).
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import object_session

from app.api import not_found
from app.deps import DB, SettingsDep
from app.models import Company, MergedRecord, Team


def calling_app(
    settings: SettingsDep,
    x_bishnoi_key: Annotated[str | None, Header()] = None,
    # The header's name before the rename to Bishnoi One: still taken until every app is redeployed.
    x_nabhi_key: Annotated[str | None, Header()] = None,
) -> str:
    """The name of the app whose key came with the request."""
    x_bishnoi_key = x_bishnoi_key or x_nabhi_key
    if x_bishnoi_key:
        for key in settings.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if hmac.compare_digest(secret.encode(), x_bishnoi_key.encode()):
                return name
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This needs a Bishnoi One app's key (X-Bishnoi-Key).")


Caller = Annotated[str, Depends(calling_app)]
router = APIRouter(prefix="/integration/customers", tags=["integration"])


def customer_out(c: Company) -> dict:
    tin = (c.extra or {}).get("tin")
    return {
        "id": c.id,
        "no": c.no,
        "name": c.name,
        "status": c.status,
        "address": ", ".join(p for p in (c.address, c.city) if p) or None,
        "email": c.email,
        "phone": c.phone,
        "tin": tin if isinstance(tin, str) and tin.strip() else None,
        # Whose customer it is: Finance puts them on the invoice as the salesperson, whose sale it scores.
        "owner": owner_out(c.owner) if c.owner else None,
    }


def owner_out(user) -> dict:
    """The salesperson, with their team and the division above it: the company's org chart, whose
    units the CRM's teams are a copy of (app/platform_org.py). Finance keeps them on the invoice."""
    team = user.team
    division = object_session(user).get(Team, team.parent_id) if team is not None and team.parent_id else team
    return {
        "id": user.id,
        "name": user.full_name,
        "team": {"id": team.id, "name": team.name} if team is not None and team.parent_id else None,
        "division": {"id": division.id, "name": division.name} if division is not None else None,
    }


@router.get("")
def find_customers(_: Caller, db: DB, q: str | None = Query(None, max_length=100), limit: int = Query(20, ge=1, le=100)) -> dict:
    """Customers by name, email or phone, alphabetically."""
    query = select(Company).order_by(func.lower(Company.name)).limit(limit)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Company.name).like(like), func.lower(Company.email).like(like), Company.phone.like(like)))
    return {"items": [customer_out(c) for c in db.scalars(query)]}


@router.get("/{customer_id}")
def read_customer(_: Caller, db: DB, customer_id: str) -> dict:
    c = db.get(Company, customer_id)
    if c is None and (merged := db.get(MergedRecord, customer_id)) is not None and merged.kind == "company":
        # Merged into another: that one answers, under its own id, so the
        # calling app can save the new id.
        c = db.get(Company, merged.new_id)
    if c is None:
        raise not_found("customer")
    return customer_out(c)
