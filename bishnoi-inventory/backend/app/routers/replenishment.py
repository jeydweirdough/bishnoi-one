"""Replenishment (feature plan step 15a, app/replenishment.py).

    GET /inventory/replenishment?warehouse=&all=     what to order now (or every item), and the settings
    POST /inventory/replenishment/drafts             {warehouseId, productIds?}: draft purchase orders per vendor
    PUT /inventory/replenishment/settings            safety days, default lead time, days of use, automatic at night
"""

from fastapi import APIRouter, Query, Request
from pydantic import Field

from app import replenishment as rp
from app.access import allowed
from app.api import Api, field_error
from app.audit import audit
from app.deps import DB, CurrentUser
from app.out import warehouse_ref

router = APIRouter(prefix="/inventory", tags=["replenishment"])


@router.get("/replenishment")
def replenishment(_: allowed("purchasing.view"), db: DB, warehouse: str | None = Query(None, max_length=36), all: bool = False) -> dict:  # noqa: A002
    w = rp.warehouse_of(db, warehouse)
    if w is None:
        return {"warehouse": None, "rows": [], "settings": rp.settings_out(rp.settings_of(db))}
    rows = rp.plan(db, w, everything=all)
    return {"warehouse": warehouse_ref(w), "rows": rows, "settings": rp.settings_out(rp.settings_of(db)),
            "due": sum(1 for r in rows if r["suggested"] > 0), "needVendor": sum(1 for r in rows if r["suggested"] > 0 and r["supplier"] is None)}


class DraftsIn(Api):
    warehouse_id: str = Field(max_length=36)
    product_ids: list[str] | None = Field(None, max_length=2000)


@router.post("/replenishment/drafts")
def drafts(_: allowed("purchasing.create"), me: CurrentUser, db: DB, body: DraftsIn) -> dict:
    w = rp.warehouse_of(db, body.warehouse_id)
    if w is None or not w.is_active:
        raise field_error("warehouseId", "Pick a warehouse that's switched on.")
    made, no_vendor = rp.make_drafts(db, me, w, body.product_ids)
    for po in made:
        audit(db, me, "purchase_order.created", target=po.number, target_type="purchase_order", target_id=po.id, fields=["by replenishment"])
    db.commit()
    return {"made": [{"id": po.id, "number": po.number, "supplier": po.supplier.name if po.supplier else None, "lines": len(po.lines)} for po in made],
            "needVendor": [r["product"] for r in no_vendor]}


class SettingsIn(Api):
    safety_days: int = Field(ge=0, le=365)
    default_lead_days: int = Field(ge=0, le=365)
    history_days: int = Field(ge=7, le=730)
    automatic: bool = False


@router.put("/replenishment/settings")
def change_settings(_: allowed("purchasing.approve"), me: CurrentUser, db: DB, body: SettingsIn) -> dict:
    s = rp.settings_of(db)
    fields = [k for k, v in (("safety_days", body.safety_days), ("default_lead_days", body.default_lead_days), ("history_days", body.history_days), ("automatic", body.automatic)) if getattr(s, k) != v]
    s.safety_days, s.default_lead_days, s.history_days, s.automatic = body.safety_days, body.default_lead_days, body.history_days, body.automatic
    if fields:
        audit(db, me, "replenishment.settings_changed", target="replenishment", target_type="settings", fields=fields)
    db.commit()
    return rp.settings_out(s)


# --- consignment settlements (step 15d): paying vendors for what sold ----------------------------------


@router.get("/consignment")
def consignment(_: allowed("purchasing.view"), db: DB) -> dict:
    from app.consignment import overview

    return {"vendors": overview(db)}


@router.post("/consignment/{supplier_id}/settle")
def settle_consignment(_: allowed("purchasing.approve"), me: CurrentUser, db: DB, supplier_id: str, request: Request) -> dict:
    """What sold from the vendor's consignment since its last settlement: recorded, and sent to Finance as a draft bill."""
    from app.api import found
    from app.consignment import settle
    from app.models import Supplier

    s = settle(db, me, found(db, Supplier, supplier_id, "vendor"), getattr(request.state, "company", None))
    audit(db, me, "consignment.settled", target=f"{s.number} · {s.supplier.name}", target_type="consignment_settlement", target_id=s.id)
    db.commit()
    return {"id": s.id, "number": s.number, "total": s.total, "lines": s.lines}
