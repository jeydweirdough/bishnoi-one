"""Packages and wave picking (feature plan step 14d, 2026-10-29): pick → pack → ship.

Packages: a delivery's boxes, numbered (PK-), each holding part of its lines, with a label to print.
Packed from when its stock is held until it's delivered; each line can't be packed beyond its quantity.

    GET    /inventory/orders/{id}/packages
    POST   /inventory/orders/{id}/packages               {lines: [{lineId, quantity}]} (none: everything not packed yet), weightKg, notes
    DELETE /inventory/orders/{id}/packages/{package_id}

Waves: several held deliveries from one warehouse picked together (WV-): one pick list, each product's total
and where to take it from (first expired, first out), and which delivery each part goes to. Starting a wave
starts picking its deliveries; done, they're picked and ready to issue.

    GET  /inventory/waves                  open first
    POST /inventory/waves                  {orderIds, notes}
    GET  /inventory/waves/{id}             its pick list
    POST /inventory/waves/{id}/done
    POST /inventory/waves/{id}/remove      {orderId}: a delivery taken out of it
"""

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import select

from app.access import CurrentAccess, allowed
from app.api import Api, conflict, field_error, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Order, Package, PackageLine, Product, Wave
from app.out import person, product_ref, warehouse_ref
from app.stock import fefo, next_number

router = APIRouter(prefix="/inventory", tags=["packing and waves"])

PACKABLE = ("confirmed", "picking", "issued")
HELD = ("confirmed", "picking")


# --- packages ----------------------------------------------------------------------------------


def packed(o: Order, packages: list[Package]) -> dict[str, int]:
    """How much of each of its lines is already in a box."""
    out: dict[str, int] = defaultdict(int)
    for p in packages:
        for line in p.lines:
            out[line.order_line_id] += line.quantity
    return out


def package_out(o: Order, p: Package, index: int, of: int) -> dict:
    lines = {line.id: line for line in o.lines}
    return {
        "id": p.id, "number": p.number, "index": index, "of": of, "weightGrams": p.weight_grams, "notes": p.notes,
        "packedBy": person(p.packed_by), "createdAt": iso(p.created_at),
        "lines": [{"lineId": pl.order_line_id, "product": product_ref(lines[pl.order_line_id].product), "quantity": pl.quantity}
                  for pl in p.lines if pl.order_line_id in lines],
    }


def packages_of(db: DB, o: Order) -> list[Package]:
    return list(db.scalars(select(Package).where(Package.order_id == o.id).order_by(Package.created_at, Package.number)))


def packing_out(db: DB, o: Order) -> dict:
    packages = packages_of(db, o)
    done = packed(o, packages)
    return {
        "packages": [package_out(o, p, i + 1, len(packages)) for i, p in enumerate(packages)],
        "lines": [{"lineId": line.id, "product": product_ref(line.product), "quantity": line.quantity, "packed": done.get(line.id, 0)} for line in o.lines],
        "allPacked": all(done.get(line.id, 0) >= line.quantity for line in o.lines),
    }


@router.get("/orders/{order_id}/packages")
def list_packages(_: allowed("orders.view"), db: DB, order_id: str) -> dict:
    return packing_out(db, found(db, Order, order_id, "order"))


class PackLineIn(Api):
    line_id: str = Field(max_length=36)
    quantity: int = Field(gt=0, le=10**9)


class PackageIn(Api):
    lines: list[PackLineIn] = Field(default_factory=list, max_length=500)
    weight_kg: float | None = Field(None, gt=0, le=100000)
    notes: str | None = Field(None, max_length=300)


@router.post("/orders/{order_id}/packages", status_code=status.HTTP_201_CREATED)
def pack(_: allowed("orders.issue"), me: CurrentUser, db: DB, order_id: str, body: PackageIn) -> dict:
    o = found(db, Order, order_id, "order")
    if o.status not in PACKABLE or o.delivery_status == "delivered":
        raise conflict("Pack a delivery once its stock is held, and before it's delivered.")
    done = packed(o, packages_of(db, o))
    lines = {line.id: line for line in o.lines}
    wanted = [(x.line_id, x.quantity) for x in body.lines] or [(line.id, line.quantity - done.get(line.id, 0)) for line in o.lines]
    wanted = [(lid, q) for lid, q in wanted if q > 0]
    if not wanted:
        raise conflict("Everything on this delivery is already packed.")
    p = Package(number=next_number(db, "PK"), order_id=o.id, packed_by_id=me.id, notes=(body.notes or "").strip() or None,
                weight_grams=round(body.weight_kg * 1000) if body.weight_kg else None)
    for i, (lid, quantity) in enumerate(wanted):
        line = lines.get(lid)
        if line is None:
            raise field_error(f"lines.{i}.lineId", "That line isn't on this delivery.")
        left = line.quantity - done.get(lid, 0)
        if quantity > left:
            raise field_error(f"lines.{i}.quantity", f"Only {left} of {line.product.name} {'is' if left == 1 else 'are'} left to pack.")
        done[lid] = done.get(lid, 0) + quantity
        p.lines.append(PackageLine(order_line_id=lid, quantity=quantity))
    db.add(p)
    db.flush()
    audit(db, me, "order.packed", target=f"{o.number} · {p.number}", target_type="order", target_id=o.id)
    db.commit()
    return packing_out(db, o)


@router.delete("/orders/{order_id}/packages/{package_id}")
def unpack(_: allowed("orders.issue"), me: CurrentUser, db: DB, order_id: str, package_id: str) -> dict:
    o = found(db, Order, order_id, "order")
    p = found(db, Package, package_id, "package")
    if p.order_id != o.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That package isn't this delivery's.")
    if o.delivery_status == "delivered":
        raise conflict("This delivery is delivered: its packages stay as they were.")
    audit(db, me, "order.unpacked", target=f"{o.number} · {p.number}", target_type="order", target_id=o.id)
    db.delete(p)
    db.commit()
    return packing_out(db, o)


# --- waves -------------------------------------------------------------------------------------


def wave_orders(db: DB, w: Wave) -> list[Order]:
    return list(db.scalars(select(Order).where(Order.wave_id == w.id).order_by(Order.number)))


def wave_out(db: DB, w: Wave, *, full: bool = True) -> dict:
    orders = wave_orders(db, w)
    out = {
        "id": w.id, "number": w.number, "status": w.status, "warehouse": warehouse_ref(w.warehouse), "notes": w.notes,
        "createdBy": person(w.created_by), "createdAt": iso(w.created_at), "doneAt": iso(w.done_at),
        "orders": [{"id": o.id, "number": o.number, "recipient": o.recipient, "status": o.status, "units": sum(line.quantity for line in o.lines)} for o in orders],
        "units": sum(line.quantity for o in orders for line in o.lines),
    }
    if full:
        out["pickList"] = pick_list(db, w, orders)
    return out


def pick_list(db: DB, w: Wave, orders: list[Order]) -> list[dict]:
    """Each product once: the total, where to take it (first expired, first out), and how it splits between deliveries."""
    by: dict[str, dict] = {}
    for o in orders:
        for line in o.lines:
            r = by.setdefault(line.product_id, {"product": line.product, "total": 0, "orders": []})
            r["total"] += line.quantity
            r["orders"].append({"orderId": o.id, "number": o.number, "recipient": o.recipient, "quantity": line.quantity})
    rows = []
    for r in by.values():
        product: Product = r["product"]
        try:
            places = [{"location": {"id": row.location.id, "code": row.location.code}, "batch": {"id": row.batch.id, "batchNo": row.batch.batch_no,
                       "expiresOn": row.batch.expires_on.isoformat() if row.batch and row.batch.expires_on else None} if row.batch else None, "quantity": take}
                      for row, take in fefo(db, product, w.warehouse_id, r["total"])]
            short = 0
        except HTTPException:
            places, short = [], r["total"]
        rows.append({"product": product_ref(product), "total": r["total"], "from": places, "short": short, "orders": r["orders"]})
    rows.sort(key=lambda r: (r["from"][0]["location"]["code"] if r["from"] else "~", r["product"]["name"].lower()))
    return rows


@router.get("/waves")
def list_waves(_: allowed("orders.view"), db: DB) -> dict:
    waves = db.scalars(select(Wave).order_by((Wave.status == "done"), Wave.created_at.desc()).limit(200)).all()
    return {"items": [wave_out(db, w, full=False) for w in waves]}


class WaveIn(Api):
    order_ids: list[str] = Field(min_length=1, max_length=200)
    notes: str | None = Field(None, max_length=300)


@router.post("/waves", status_code=status.HTTP_201_CREATED)
def make_wave(access: CurrentAccess, me: CurrentUser, db: DB, body: WaveIn) -> dict:
    """The deliveries picked together: held, one warehouse, not in another open wave. Their picking starts."""
    access.require("orders.issue")
    orders = [found(db, Order, oid, "order") for oid in dict.fromkeys(body.order_ids)]
    warehouses = {o.warehouse_id for o in orders}
    if len(warehouses) > 1:
        raise field_error("orderIds", "A wave picks from one warehouse: pick deliveries from the same one.")
    for o in orders:
        if o.status not in HELD:
            raise field_error("orderIds", f"{o.number} is {o.status}: only deliveries with their stock held are picked.")
        if o.wave_id:
            other = db.get(Wave, o.wave_id)
            if other is not None and other.status == "open":
                raise field_error("orderIds", f"{o.number} is already in {other.number}.")
    w = Wave(number=next_number(db, "WV"), warehouse_id=orders[0].warehouse_id, created_by_id=me.id, notes=(body.notes or "").strip() or None)
    db.add(w)
    db.flush()
    for o in orders:
        o.wave_id = w.id
        if o.status == "confirmed":
            o.status = "picking"  # reserved stock becomes allocated, as Start picking does
    audit(db, me, "wave.created", target=w.number, target_type="wave", target_id=w.id, fields=[o.number for o in orders])
    db.commit()
    return wave_out(db, w)


@router.get("/waves/{wave_id}")
def read_wave(_: allowed("orders.view"), db: DB, wave_id: str) -> dict:
    return wave_out(db, found(db, Wave, wave_id, "wave"))


@router.post("/waves/{wave_id}/done")
def wave_done(_: allowed("orders.issue"), me: CurrentUser, db: DB, wave_id: str) -> dict:
    w = found(db, Wave, wave_id, "wave")
    if w.status != "open":
        raise conflict(f"{w.number} is already done.")
    w.status, w.done_at = "done", datetime.now(UTC)
    audit(db, me, "wave.done", target=w.number, target_type="wave", target_id=w.id)
    db.commit()
    return wave_out(db, w)


class RemoveIn(Api):
    order_id: str = Field(max_length=36)


@router.post("/waves/{wave_id}/remove")
def remove_from_wave(_: allowed("orders.issue"), me: CurrentUser, db: DB, wave_id: str, body: RemoveIn) -> dict:
    w = found(db, Wave, wave_id, "wave")
    o = found(db, Order, body.order_id, "order")
    if o.wave_id != w.id:
        raise field_error("orderId", f"{o.number} isn't in {w.number}.")
    if w.status != "open":
        raise conflict(f"{w.number} is done.")
    o.wave_id = None
    audit(db, me, "wave.order_removed", target=w.number, target_type="wave", target_id=w.id, fields=[o.number])
    db.commit()
    return wave_out(db, w)


@router.delete("/waves/{wave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wave(_: allowed("orders.issue"), me: CurrentUser, db: DB, wave_id: str) -> Response:
    """An open wave, let go: its deliveries stay as they are (picking), out of any wave."""
    w = found(db, Wave, wave_id, "wave")
    if w.status != "open":
        raise conflict(f"{w.number} is done: it's kept.")
    for o in wave_orders(db, w):
        o.wave_id = None
    audit(db, me, "wave.deleted", target=w.number, target_type="wave", target_id=w.id)
    db.delete(w)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
