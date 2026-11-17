"""Packages (feature plan step 14d, 2026-10-29): pick → pack → ship.

Packages: a delivery's boxes, numbered (PK-), each holding part of its lines, with a label to print.
Packed from when its stock is held until it's delivered; each line can't be packed beyond its quantity.

    GET    /inventory/orders/{id}/packages
    POST   /inventory/orders/{id}/packages               {lines: [{lineId, quantity}]} (none: everything not packed yet), weightKg, notes
    DELETE /inventory/orders/{id}/packages/{package_id}

Wave picking was removed on 2026-11-17 (owner's decision); each delivery is picked on its own.
"""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, status
from pydantic import Field
from sqlalchemy import select

from app.access import allowed
from app.api import Api, conflict, field_error, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Order, Package, PackageLine
from app.out import person, product_ref
from app.stock import next_number

router = APIRouter(prefix="/inventory", tags=["packing"])

PACKABLE = ("confirmed", "picking", "issued")


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

