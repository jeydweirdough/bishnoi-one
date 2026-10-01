"""What other Nabhi apps may read from the CRM: its customers, for Finance to
invoice. Only for an app holding one of INTEGRATION_KEYS, sent in the
X-Nabhi-Key header (the same way the CRM reads Inventory and asks Finance).

Read-only, and only what an invoice needs: who the customer is, where they
are, how to reach them, and their TIN when the company keeps one (an added
field named "tin" on the customer form).
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api import not_found
from app.deps import DB, SettingsDep
from app.models import Company


def calling_app(settings: SettingsDep, x_nabhi_key: Annotated[str | None, Header()] = None) -> str:
    """The name of the app whose key came with the request."""
    if x_nabhi_key:
        for key in settings.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if hmac.compare_digest(secret.encode(), x_nabhi_key.encode()):
                return name
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This needs a Nabhi app's key (X-Nabhi-Key).")


Caller = Annotated[str, Depends(calling_app)]
router = APIRouter(prefix="/integration/customers", tags=["integration"])


def customer_out(c: Company) -> dict:
    tin = (c.extra or {}).get("tin")
    return {
        "id": c.id,
        "name": c.name,
        "status": c.status,
        "address": ", ".join(p for p in (c.address, c.city) if p) or None,
        "email": c.email,
        "phone": c.phone,
        "tin": tin if isinstance(tin, str) and tin.strip() else None,
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
    if c is None:
        raise not_found("customer")
    return customer_out(c)
