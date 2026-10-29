"""Consignment settlements (feature plan step 15d, finished 2026-10-29): paying vendors for what sold.

A vendor's consignment stock sits in its own location in each warehouse (CON-<code>). What was issued from it
since the vendor's last settlement is what we owe, at the vendor's price for the item (else its cost).
Settling records it once (CS-…) and tells Finance, which makes a draft vendor bill (event consignment.billed);
the next settlement starts where this one ended.
"""

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import business_events
from app.api import conflict
from app.models import ConsignmentSettlement, Location, Movement, Product, Supplier, SupplierProduct, User
from app.stock import next_number


def last(db: Session, supplier_id: str) -> ConsignmentSettlement | None:
    return db.scalar(select(ConsignmentSettlement).where(ConsignmentSettlement.supplier_id == supplier_id).order_by(ConsignmentSettlement.to_at.desc()))


def unsettled(db: Session, supplier: Supplier, until: datetime | None = None) -> tuple[datetime | None, list[dict]]:
    """(since when, each item sold from its consignment since then: quantity, the vendor's price, total)."""
    since = (prev.to_at if (prev := last(db, supplier.id)) else None)
    locations = [loc.id for loc in db.scalars(select(Location).where(Location.consignment_supplier_id == supplier.id))]
    if not locations:
        return since, []
    q = select(Movement.product_id, func.sum(-Movement.quantity)).where(Movement.kind == "issue", Movement.location_id.in_(locations))
    if since is not None:
        q = q.where(Movement.at > since)
    if until is not None:
        q = q.where(Movement.at <= until)
    sold: dict[str, int] = defaultdict(int)
    for pid, n in db.execute(q.group_by(Movement.product_id)):
        sold[pid] += int(n or 0)
    rows = []
    for pid, quantity in sold.items():
        if quantity <= 0:
            continue
        p = db.get(Product, pid)
        terms = db.get(SupplierProduct, (supplier.id, pid))
        price = terms.price if terms and terms.price else p.cost_price
        rows.append({"productId": pid, "sku": p.sku, "name": p.name, "quantity": quantity, "unitCost": price, "total": quantity * price})
    rows.sort(key=lambda r: r["name"].lower())
    return since, rows


def settle(db: Session, me: User, supplier: Supplier, slug: str | None) -> ConsignmentSettlement:
    now = datetime.now(UTC)
    since, rows = unsettled(db, supplier, now)
    if not rows:
        raise conflict(f"Nothing of {supplier.name}'s consignment has sold since its last settlement.")
    s = ConsignmentSettlement(number=next_number(db, "CS"), supplier_id=supplier.id, from_at=since, to_at=now, lines=rows,
                              total=sum(r["total"] for r in rows), created_by_id=me.id)
    db.add(s)
    db.flush()
    business_events.emit(db, slug, "consignment.billed", {
        "settlementId": s.id, "number": s.number, "from": since.isoformat() if since else None, "to": now.isoformat(),
        "supplier": {"id": supplier.id, "code": supplier.code, "name": supplier.name, "tin": getattr(supplier, "tin", None), "email": supplier.email},
        "lines": rows, "totalCentavos": s.total,
    })
    return s


def overview(db: Session) -> list[dict]:
    """Every vendor with consignment: unsettled sales and what they come to, and its settlements."""
    vendor_ids = {loc.consignment_supplier_id for loc in db.scalars(select(Location).where(Location.consignment_supplier_id.is_not(None)))}
    out = []
    for sid in vendor_ids:
        supplier = db.get(Supplier, sid)
        if supplier is None:
            continue
        since, rows = unsettled(db, supplier)
        settlements = db.scalars(select(ConsignmentSettlement).where(ConsignmentSettlement.supplier_id == sid).order_by(ConsignmentSettlement.to_at.desc()).limit(12)).all()
        out.append({"supplier": {"id": supplier.id, "code": supplier.code, "name": supplier.name}, "since": since.isoformat() if since else None,
                    "lines": rows, "toPay": sum(r["total"] for r in rows),
                    "settlements": [{"id": x.id, "number": x.number, "from": x.from_at.isoformat() if x.from_at else None, "to": x.to_at.isoformat(),
                                     "total": x.total, "lines": len(x.lines)} for x in settlements]})
    out.sort(key=lambda r: r["supplier"]["name"].lower())
    return out
