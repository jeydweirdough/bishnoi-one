"""Suppliers: who the pharmacy buys from, and what each has delivered."""

from fastapi import APIRouter, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select

from app.access import Can
from app.api import Api, camel, changed, check_email, conflict, day, field_error, get_or_404, iso
from app.audit import audit
from app.deps import DB
from app.models import Batch, Receiving, Supplier

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


class SupplierIn(Api):
    name: str = Field(min_length=1, max_length=160)
    contact_person: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=254)
    address: str | None = Field(None, max_length=300)
    notes: str | None = Field(None, max_length=4000)
    is_active: bool = True

    _email = field_validator("email")(check_email)


class SupplierPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=160)
    contact_person: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=254)
    address: str | None = Field(None, max_length=300)
    notes: str | None = Field(None, max_length=4000)
    is_active: bool | None = None

    _email = field_validator("email")(check_email)


def supplier_out(s: Supplier, deliveries: int = 0, last: object = None) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "contactPerson": s.contact_person,
        "phone": s.phone,
        "email": s.email,
        "address": s.address,
        "notes": s.notes,
        "isActive": s.is_active,
        "deliveryCount": deliveries,
        "lastDeliveryOn": day(last),
        "updatedAt": iso(s.updated_at),
    }


def _name_taken(db: DB, name: str, but: str | None = None) -> bool:
    q = select(Supplier.id).where(func.lower(Supplier.name) == name.lower())
    if but:
        q = q.where(Supplier.id != but)
    return db.scalar(q) is not None


@router.get("")
def list_suppliers(_: Can("suppliers.view"), db: DB, q: str | None = Query(None, max_length=80), state: str = "active") -> list[dict]:
    query = select(Supplier).order_by(func.lower(Supplier.name))
    if state in ("active", "off"):
        query = query.where(Supplier.is_active.is_(state == "active"))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Supplier.name).like(like), func.lower(Supplier.contact_person).like(like)))
    stats = {
        sid: (n, last)
        for sid, n, last in db.execute(
            select(Receiving.supplier_id, func.count(), func.max(Receiving.received_on)).group_by(Receiving.supplier_id)
        ).all()
    }
    return [supplier_out(s, *stats.get(s.id, (0, None))) for s in db.scalars(query)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_supplier(access: Can("suppliers.create"), db: DB, body: SupplierIn) -> dict:
    if _name_taken(db, body.name):
        raise field_error("name", "There's already a supplier with that name.")
    s = Supplier(**body.model_dump())
    db.add(s)
    db.flush()
    audit(db, access.user, "supplier.created", target=s.name, target_type="supplier", target_id=s.id)
    db.commit()
    return supplier_out(s)


@router.get("/{supplier_id}")
def read_supplier(_: Can("suppliers.view"), db: DB, supplier_id: str) -> dict:
    s = get_or_404(db, Supplier, supplier_id, "supplier")
    deliveries = list(db.scalars(select(Receiving).where(Receiving.supplier_id == s.id).order_by(Receiving.received_on.desc()).limit(50)))
    batches = db.scalars(select(Batch).where(Batch.supplier_id == s.id, Batch.qty_on_hand > 0).order_by(Batch.expires_on).limit(100))
    return {
        **supplier_out(s, len(deliveries), deliveries[0].received_on if deliveries else None),
        "deliveries": [{"id": r.id, "number": r.number, "reference": r.reference, "receivedOn": day(r.received_on)} for r in deliveries],
        "batches": [
            {"id": b.id, "medicine": b.medicine.label, "lotNo": b.lot_no, "expiresOn": day(b.expires_on), "qtyOnHand": b.qty_on_hand, "status": b.status}
            for b in batches
        ],
    }


@router.patch("/{supplier_id}")
def update_supplier(access: Can("suppliers.edit"), db: DB, supplier_id: str, body: SupplierPatch) -> dict:
    s = get_or_404(db, Supplier, supplier_id, "supplier")
    wanted = changed(body)
    for key in ("name", "is_active"):
        if key in wanted and wanted[key] is None:
            raise field_error(camel([key])[0], "This can't be empty.")
    if "name" in wanted and _name_taken(db, wanted["name"], but=s.id):
        raise field_error("name", "There's already a supplier with that name.")
    fields = [k for k, v in wanted.items() if getattr(s, k) != v]
    for k in fields:
        setattr(s, k, wanted[k])
    if fields:
        audit(db, access.user, "supplier.updated", target=s.name, target_type="supplier", target_id=s.id, fields=camel(fields))
        db.commit()
    return supplier_out(s)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(access: Can("suppliers.delete"), db: DB, supplier_id: str) -> Response:
    s = get_or_404(db, Supplier, supplier_id, "supplier")
    if db.scalar(select(func.count()).select_from(Receiving).where(Receiving.supplier_id == s.id)):
        raise conflict(f"{s.name} has deliveries on record. Switch them off instead.")
    audit(db, access.user, "supplier.deleted", target=s.name, target_type="supplier", target_id=s.id)
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
