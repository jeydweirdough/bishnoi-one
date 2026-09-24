"""Warehouses, and the locations (zones, racks, bins) inside them.

Every warehouse has one default location, made with it, where stock goes
when nobody says otherwise. A place that has held stock is switched off
rather than deleted, so its history still reads.
"""

from fastapi import APIRouter, Response, status
from pydantic import Field
from sqlalchemy import func, select

from app.access import allowed
from app.api import Api, changed, conflict, field_error, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser
from app.levels import ZERO, by_warehouse
from app.models import Location, Movement, Product, Stock, Warehouse
from app.out import warehouse_ref

router = APIRouter(prefix="/inventory", tags=["warehouses"])

View = allowed("warehouses.view")
Manage = allowed("warehouses.manage")

CODE = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"


class WarehouseIn(Api):
    code: str = Field(min_length=1, max_length=20, pattern=CODE)
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(None, max_length=300)


class WarehousePatch(Api):
    code: str | None = Field(None, min_length=1, max_length=20, pattern=CODE)
    name: str | None = Field(None, min_length=1, max_length=120)
    address: str | None = Field(None, max_length=300)
    is_active: bool | None = None


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
        "isActive": w.is_active,
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
    warehouse = Warehouse(code=body.code.upper(), name=body.name, address=body.address)
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
