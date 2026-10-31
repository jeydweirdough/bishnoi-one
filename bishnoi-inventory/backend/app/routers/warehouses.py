"""Warehouses, and the locations (zones, racks, bins) inside them.

Every warehouse has one default location, made with it, where stock goes
when nobody says otherwise. A place that has held stock is switched off
rather than deleted, so its history still reads.
"""

import httpx
from fastapi import APIRouter, Response, status
from pydantic import Field
from sqlalchemy import func, select

from app import documents
from app.access import allowed, settings_allowed
from app.api import Api, changed, conflict, field_error, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser
from app.levels import ZERO, by_warehouse
from app.models import OPERATION_KINDS, Location, Movement, OperationType, Product, Stock, Warehouse
from app.out import warehouse_ref

router = APIRouter(prefix="/inventory", tags=["warehouses"])

View = allowed("warehouses.view")
# Couriers, warehouses and locations: changed by the company administrators (2026-10-31).
Manage = settings_allowed("warehouses.manage")

CODE = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"


class WarehouseIn(Api):
    code: str = Field(min_length=1, max_length=20, pattern=CODE)
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(None, max_length=300)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    # Receive → check → store (step 14a).
    quality_check: bool = False


class WarehousePatch(Api):
    code: str | None = Field(None, min_length=1, max_length=20, pattern=CODE)
    name: str | None = Field(None, min_length=1, max_length=120)
    address: str | None = Field(None, max_length=300)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    is_active: bool | None = None
    quality_check: bool | None = None


class LocationIn(Api):
    code: str = Field(min_length=1, max_length=20, pattern=CODE)
    name: str = Field(min_length=1, max_length=120)


class LocationPatch(Api):
    code: str | None = Field(None, min_length=1, max_length=20, pattern=CODE)
    name: str | None = Field(None, min_length=1, max_length=120)
    is_active: bool | None = None
    is_default: bool | None = None


def totals(db: DB) -> dict[str, dict]:
    """Per warehouse: units on hand, what they're worth, and how many products."""
    out: dict[str, dict] = {}
    rows = db.execute(
        select(Stock.warehouse_id, func.sum(Stock.on_hand), func.sum(Stock.on_hand * Product.cost_price), func.count(func.distinct(Stock.product_id)))
        .join(Product)
        .where(Stock.on_hand > 0)
        .group_by(Stock.warehouse_id)
    )
    for wh, units, value, products in rows:
        out[wh] = {"units": int(units or 0), "value": int(value or 0), "products": int(products or 0)}
    return out


def warehouse_out(w: Warehouse, total: dict | None, locations: int) -> dict:
    return {
        **warehouse_ref(w),
        "address": w.address,
        "latitude": w.latitude,
        "longitude": w.longitude,
        "isActive": w.is_active,
        "qualityCheck": w.quality_check,
        "locationCount": locations,
        "units": (total or {}).get("units", 0),
        "value": (total or {}).get("value", 0),
        "products": (total or {}).get("products", 0),
    }


def code_taken(db: DB, code: str, but: str | None = None) -> bool:
    q = select(Warehouse.id).where(func.lower(Warehouse.code) == code.lower())
    return db.scalar(q.where(Warehouse.id != but) if but else q) is not None


@router.get("/warehouses")
def list_warehouses(_: View, db: DB) -> list[dict]:
    t = totals(db)
    counts = dict(db.execute(select(Location.warehouse_id, func.count()).group_by(Location.warehouse_id)).all())
    return [warehouse_out(w, t.get(w.id), counts.get(w.id, 0)) for w in db.scalars(select(Warehouse).order_by(Warehouse.is_active.desc(), Warehouse.code))]


@router.post("/warehouses", status_code=status.HTTP_201_CREATED)
def create_warehouse(_: Manage, me: CurrentUser, db: DB, body: WarehouseIn) -> dict:
    if code_taken(db, body.code):
        raise field_error("code", "Another warehouse has that code.")
    warehouse = Warehouse(code=body.code.upper(), name=body.name, address=body.address, quality_check=body.quality_check)
    db.add(warehouse)
    db.flush()
    db.add(Location(warehouse_id=warehouse.id, code="MAIN", name="Main area", is_default=True))
    audit(db, me, "warehouse.created", target=warehouse.name, target_type="warehouse", target_id=warehouse.id)
    db.commit()
    return {"id": warehouse.id}


@router.get("/warehouses/{warehouse_id}")
def read_warehouse(_: View, db: DB, warehouse_id: str) -> dict:
    w = found(db, Warehouse, warehouse_id, "warehouse")
    locations = db.scalars(select(Location).where(Location.warehouse_id == w.id).order_by(Location.is_default.desc(), Location.code)).all()
    per_location = dict(
        (loc, (int(units or 0), int(products or 0)))
        for loc, units, products in db.execute(
            select(Stock.location_id, func.sum(Stock.on_hand), func.count(func.distinct(Stock.product_id)))
            .where(Stock.warehouse_id == w.id, Stock.on_hand > 0)
            .group_by(Stock.location_id)
        )
    )
    levels = by_warehouse(db, warehouse_id=w.id)
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_([p for p, _ in levels])))}
    summary = dict(ZERO)
    for row in levels.values():
        for k, v in row.items():
            summary[k] += v
    return {
        **warehouse_out(w, totals(db).get(w.id), len(locations)),
        "createdAt": iso(w.created_at),
        "summary": summary,
        "locations": [
            {
                "id": loc.id,
                "code": loc.code,
                "name": loc.name,
                "isDefault": loc.is_default,
                "isActive": loc.is_active,
                "units": per_location.get(loc.id, (0, 0))[0],
                "products": per_location.get(loc.id, (0, 0))[1],
            }
            for loc in locations
        ],
        "lowCount": sum(
            1
            for (pid, _), row in levels.items()
            if pid in products and row["available"] <= products[pid].reorder_point and products[pid].status == "active"
        ),
    }


@router.patch("/warehouses/{warehouse_id}")
def update_warehouse(_: Manage, me: CurrentUser, db: DB, warehouse_id: str, body: WarehousePatch) -> dict:
    w = found(db, Warehouse, warehouse_id, "warehouse")
    wanted = changed(body)
    for key in ("code", "name", "is_active"):
        if key in wanted and wanted[key] is None:
            raise field_error(key, "This can't be empty.")
    if "code" in wanted:
        wanted["code"] = wanted["code"].upper()
        if code_taken(db, wanted["code"], but=w.id):
            raise field_error("code", "Another warehouse has that code.")
    if wanted.get("is_active") is False:
        held = db.scalar(select(func.coalesce(func.sum(Stock.on_hand), 0)).where(Stock.warehouse_id == w.id)) or 0
        if held:
            raise conflict(f"{held} units are still here. Move them out before switching the warehouse off.")
    fields = [k for k, v in wanted.items() if getattr(w, k) != v]
    for k in fields:
        setattr(w, k, wanted[k])
    if fields:
        audit(db, me, "warehouse.updated", target=w.name, target_type="warehouse", target_id=w.id, fields=fields)
        db.commit()
    return {"id": w.id}


GEOCODER = "https://nominatim.openstreetmap.org/search"


@router.post("/warehouses/{warehouse_id}/locate")
def locate_warehouse(_: Manage, me: CurrentUser, db: DB, warehouse_id: str) -> dict:
    """Finds the warehouse's pin from its address (OpenStreetMap's own search), once, and keeps it."""
    w = found(db, Warehouse, warehouse_id, "warehouse")
    if not (w.address or "").strip():
        raise field_error("address", "Add the warehouse's address first, then find it on the map.")
    try:
        r = httpx.get(
            GEOCODER,
            params={"q": w.address, "format": "json", "limit": 1, "countrycodes": "ph"},
            headers={"User-Agent": "Bishnoi One Inventory (warehouse pins)"},
            timeout=10,
        )
        hits = r.json() if r.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        raise conflict("The map search isn't answering right now. Try again in a moment, or set the pin by hand.") from None
    if not hits:
        raise conflict(f"No place on the map matches \"{w.address}\". Make the address fuller, or set the pin by hand.")
    w.latitude, w.longitude = float(hits[0]["lat"]), float(hits[0]["lon"])
    audit(db, me, "warehouse.updated", target=w.name, target_type="warehouse", target_id=w.id, fields=["latitude", "longitude"])
    db.commit()
    return {"id": w.id, "latitude": w.latitude, "longitude": w.longitude}


@router.delete("/warehouses/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warehouse(_: Manage, me: CurrentUser, db: DB, warehouse_id: str) -> Response:
    w = found(db, Warehouse, warehouse_id, "warehouse")
    if db.scalar(select(func.count()).select_from(Movement).where(Movement.warehouse_id == w.id)):
        raise conflict("Stock has moved through this warehouse, and its history must be kept. Switch it off instead.")
    audit(db, me, "warehouse.deleted", target=w.name, target_type="warehouse", target_id=w.id)
    db.delete(w)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- locations --------------------------------------------------------------------------


def location_code_taken(db: DB, warehouse_id: str, code: str, but: str | None = None) -> bool:
    q = select(Location.id).where(Location.warehouse_id == warehouse_id, func.lower(Location.code) == code.lower())
    return db.scalar(q.where(Location.id != but) if but else q) is not None


@router.post("/warehouses/{warehouse_id}/locations", status_code=status.HTTP_201_CREATED)
def create_location(_: Manage, me: CurrentUser, db: DB, warehouse_id: str, body: LocationIn) -> dict:
    w = found(db, Warehouse, warehouse_id, "warehouse")
    if location_code_taken(db, w.id, body.code):
        raise field_error("code", "This warehouse already has a location with that code.")
    location = Location(warehouse_id=w.id, code=body.code.upper(), name=body.name)
    db.add(location)
    db.flush()
    audit(db, me, "location.created", target=f"{w.code} · {location.code}", target_type="location", target_id=location.id)
    db.commit()
    return {"id": location.id}


@router.patch("/warehouses/{warehouse_id}/locations/{location_id}")
def update_location(_: Manage, me: CurrentUser, db: DB, warehouse_id: str, location_id: str, body: LocationPatch) -> dict:
    location = found(db, Location, location_id, "location")
    if location.warehouse_id != warehouse_id:
        raise field_error("locationId", "That location isn't in this warehouse.")
    wanted = changed(body)
    for key in wanted:
        if wanted[key] is None:
            raise field_error(key, "This can't be empty.")
    if "code" in wanted:
        wanted["code"] = wanted["code"].upper()
        if location_code_taken(db, warehouse_id, wanted["code"], but=location.id):
            raise field_error("code", "This warehouse already has a location with that code.")
    if wanted.get("is_default") is False:
        raise conflict("Make another location the default instead.")
    if wanted.get("is_active") is False:
        if location.is_default or wanted.get("is_default"):
            raise conflict("The default location can't be switched off. Make another one the default first.")
        held = db.scalar(select(func.coalesce(func.sum(Stock.on_hand), 0)).where(Stock.location_id == location.id)) or 0
        if held:
            raise conflict(f"{held} units are still here. Move them before switching the location off.")
    fields = [k for k, v in wanted.items() if getattr(location, k) != v]
    if "is_default" in fields:
        for other in db.scalars(select(Location).where(Location.warehouse_id == warehouse_id, Location.is_default)):
            other.is_default = False
        db.flush()
        location.is_active = True
    for k in fields:
        setattr(location, k, wanted[k])
    if fields:
        audit(db, me, "location.updated", target=f"{location.warehouse.code} · {location.code}", target_type="location", target_id=location.id, fields=fields)
        db.commit()
    return {"id": location.id}


@router.delete("/warehouses/{warehouse_id}/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(_: Manage, me: CurrentUser, db: DB, warehouse_id: str, location_id: str) -> Response:
    location = found(db, Location, location_id, "location")
    if location.warehouse_id != warehouse_id:
        raise field_error("locationId", "That location isn't in this warehouse.")
    if location.is_default:
        raise conflict("The default location can't be deleted.")
    if db.scalar(select(func.count()).select_from(Movement).where(Movement.location_id == location.id)):
        raise conflict("Stock has moved through this location. Switch it off instead.")
    audit(db, me, "location.deleted", target=f"{location.warehouse.code} · {location.code}", target_type="location", target_id=location.id)
    db.delete(location)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- operation types (feature plan step 8): the kinds of stock document, as the company names them ---


class OperationTypeIn(Api):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field(max_length=16)
    warehouse_id: str | None = Field(None, max_length=36)
    is_default: bool = False


class OperationTypePatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    is_default: bool | None = None
    is_active: bool | None = None


@router.get("/operation-types")
def operation_types(_: CurrentUser, db: DB) -> list[dict]:
    return [documents.type_out(t) for t in db.scalars(select(OperationType).order_by(OperationType.kind, OperationType.name))]


def _one_default(db: DB, t: OperationType) -> None:
    """Only one default per kind and warehouse."""
    for other in db.scalars(select(OperationType).where(OperationType.kind == t.kind, OperationType.id != t.id, OperationType.is_default)):
        if other.warehouse_id == t.warehouse_id:
            other.is_default = False


@router.post("/operation-types", status_code=status.HTTP_201_CREATED)
def add_operation_type(_: Manage, me: CurrentUser, db: DB, body: OperationTypeIn) -> dict:
    if body.kind not in OPERATION_KINDS:
        raise field_error("kind", "Pick what kind of operation it is.")
    code = body.code.strip().upper()
    if db.scalar(select(OperationType.id).where(func.upper(OperationType.code) == code)):
        raise field_error("code", "There's already an operation type with that code.")
    if body.warehouse_id and db.get(Warehouse, body.warehouse_id) is None:
        raise field_error("warehouseId", "Pick a warehouse that exists.")
    t = OperationType(code=code, name=body.name.strip(), kind=body.kind, warehouse_id=body.warehouse_id, is_default=body.is_default)
    db.add(t)
    db.flush()
    if t.is_default:
        _one_default(db, t)
    audit(db, me, "operation_type.created", target=t.name, target_type="operation_type", target_id=t.id)
    db.commit()
    return documents.type_out(t)


@router.patch("/operation-types/{type_id}")
def change_operation_type(_: Manage, me: CurrentUser, db: DB, type_id: str, body: OperationTypePatch) -> dict:
    t = found(db, OperationType, type_id, "operation type")
    fields = {k: v for k, v in changed(body).items() if v is not None and getattr(t, k) != v}
    if fields.get("is_active") is False and t.is_default:
        raise conflict("This is the default for its kind. Make another one the default first.")
    for k, v in fields.items():
        setattr(t, k, v.strip() if isinstance(v, str) else v)
    if fields.get("is_default"):
        _one_default(db, t)
    if fields:
        audit(db, me, "operation_type.updated", target=t.name, target_type="operation_type", target_id=t.id, fields=sorted(fields))
        db.commit()
    return documents.type_out(t)
