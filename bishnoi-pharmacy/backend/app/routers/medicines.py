"""Medicines: the catalogue, their categories and brands, and each one's status.

A medicine's rx_class decides how it leaves the pharmacy: otc medicines can
be sold at the counter; rx and dangerous ones only through a verified
prescription (see routers/sales.py and routers/dispensing.py).
"""

from typing import Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.access import Can
from app.api import Api, camel, changed, conflict, day, field_error, get_or_404, iso, today
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import Batch, Brand, Category, Medicine, PrescriptionItem, SaleLine
from app.stock import on_hand, sellable

router = APIRouter(prefix="/medicines", tags=["medicines"])

RxClass = Literal["otc", "rx", "dangerous"]
Status = Literal["active", "inactive", "discontinued"]


# --- categories and brands ----------------------------------------------------------------


class CategoryIn(Api):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    is_active: bool = True


class BrandIn(Api):
    name: str = Field(min_length=1, max_length=80)
    manufacturer: str | None = Field(None, max_length=160)
    is_active: bool = True


def category_out(c: Category, count: int = 0) -> dict:
    return {"id": c.id, "name": c.name, "description": c.description, "isActive": c.is_active, "medicineCount": count}


def brand_out(b: Brand, count: int = 0) -> dict:
    return {"id": b.id, "name": b.name, "manufacturer": b.manufacturer, "isActive": b.is_active, "medicineCount": count}


def _counts(db: DB, column) -> dict[str, int]:
    return dict(db.execute(select(column, func.count()).where(column.is_not(None)).group_by(column)).all())


def _name_taken(db: DB, model, name: str, but: str | None = None) -> bool:
    q = select(model.id).where(func.lower(model.name) == name.lower())
    if but:
        q = q.where(model.id != but)
    return db.scalar(q) is not None


@router.get("/categories")
def list_categories(_: Can("medicines.view"), db: DB) -> list[dict]:
    counts = _counts(db, Medicine.category_id)
    rows = db.scalars(select(Category).order_by(Category.is_active.desc(), func.lower(Category.name)))
    return [category_out(c, counts.get(c.id, 0)) for c in rows]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(access: Can("medicines.create"), db: DB, body: CategoryIn) -> dict:
    if _name_taken(db, Category, body.name):
        raise field_error("name", "There's already a category with that name.")
    c = Category(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, access.user, "category.created", target=c.name, target_type="category", target_id=c.id)
    db.commit()
    return category_out(c)


@router.put("/categories/{category_id}")
def update_category(access: Can("medicines.edit"), db: DB, category_id: str, body: CategoryIn) -> dict:
    c = get_or_404(db, Category, category_id, "category")
    if _name_taken(db, Category, body.name, but=c.id):
        raise field_error("name", "There's already a category with that name.")
    fields = [k for k, v in body.model_dump().items() if getattr(c, k) != v]
    for k in fields:
        setattr(c, k, getattr(body, k))
    if fields:
        audit(db, access.user, "category.updated", target=c.name, target_type="category", target_id=c.id, fields=camel(fields))
        db.commit()
    return category_out(c, _counts(db, Medicine.category_id).get(c.id, 0))


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(access: Can("medicines.delete"), db: DB, category_id: str) -> Response:
    c = get_or_404(db, Category, category_id, "category")
    if db.scalar(select(func.count()).select_from(Medicine).where(Medicine.category_id == c.id)):
        raise conflict("Medicines are filed under this category. Switch it off instead, or move them first.")
    audit(db, access.user, "category.deleted", target=c.name, target_type="category", target_id=c.id)
    db.delete(c)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/brands")
def list_brands(_: Can("medicines.view"), db: DB) -> list[dict]:
    counts = _counts(db, Medicine.brand_id)
    rows = db.scalars(select(Brand).order_by(Brand.is_active.desc(), func.lower(Brand.name)))
    return [brand_out(b, counts.get(b.id, 0)) for b in rows]


@router.post("/brands", status_code=status.HTTP_201_CREATED)
def create_brand(access: Can("medicines.create"), db: DB, body: BrandIn) -> dict:
    if _name_taken(db, Brand, body.name):
        raise field_error("name", "There's already a brand with that name.")
    b = Brand(**body.model_dump())
    db.add(b)
    db.flush()
    audit(db, access.user, "brand.created", target=b.name, target_type="brand", target_id=b.id)
    db.commit()
    return brand_out(b)


@router.put("/brands/{brand_id}")
def update_brand(access: Can("medicines.edit"), db: DB, brand_id: str, body: BrandIn) -> dict:
    b = get_or_404(db, Brand, brand_id, "brand")
    if _name_taken(db, Brand, body.name, but=b.id):
        raise field_error("name", "There's already a brand with that name.")
    fields = [k for k, v in body.model_dump().items() if getattr(b, k) != v]
    for k in fields:
        setattr(b, k, getattr(body, k))
    if fields:
        audit(db, access.user, "brand.updated", target=b.name, target_type="brand", target_id=b.id, fields=camel(fields))
        db.commit()
    return brand_out(b, _counts(db, Medicine.brand_id).get(b.id, 0))


@router.delete("/brands/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(access: Can("medicines.delete"), db: DB, brand_id: str) -> Response:
    b = get_or_404(db, Brand, brand_id, "brand")
    if db.scalar(select(func.count()).select_from(Medicine).where(Medicine.brand_id == b.id)):
        raise conflict("Medicines carry this brand. Switch it off instead, or change them first.")
    audit(db, access.user, "brand.deleted", target=b.name, target_type="brand", target_id=b.id)
    db.delete(b)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- medicines --------------------------------------------------------------------------------


class MedicineIn(Api):
    code: str = Field(min_length=1, max_length=40)
    generic_name: str = Field(min_length=1, max_length=160)
    brand_id: str | None = Field(None, max_length=36)
    category_id: str | None = Field(None, max_length=36)
    strength: str | None = Field(None, max_length=40)
    dosage_form: str = Field(min_length=1, max_length=40)
    unit: str = Field("piece", min_length=1, max_length=20)
    rx_class: RxClass = "rx"
    price_centavos: int = Field(0, ge=0, le=100_000_000)
    reorder_level: int = Field(0, ge=0, le=1_000_000)
    status: Status = "active"
    notes: str | None = Field(None, max_length=4000)


class MedicinePatch(Api):
    code: str | None = Field(None, min_length=1, max_length=40)
    generic_name: str | None = Field(None, min_length=1, max_length=160)
    brand_id: str | None = Field(None, max_length=36)
    category_id: str | None = Field(None, max_length=36)
    strength: str | None = Field(None, max_length=40)
    dosage_form: str | None = Field(None, min_length=1, max_length=40)
    unit: str | None = Field(None, min_length=1, max_length=20)
    rx_class: RxClass | None = None
    price_centavos: int | None = Field(None, ge=0, le=100_000_000)
    reorder_level: int | None = Field(None, ge=0, le=1_000_000)
    status: Status | None = None
    notes: str | None = Field(None, max_length=4000)


REQUIRED = ("code", "generic_name", "dosage_form", "unit", "rx_class", "price_centavos", "reorder_level", "status")


def medicine_out(m: Medicine, stock: int | None = None, available: int | None = None) -> dict:
    return {
        "id": m.id,
        "no": m.no,
        "code": m.code,
        "genericName": m.generic_name,
        "label": m.label,
        "brand": {"id": m.brand.id, "name": m.brand.name} if m.brand else None,
        "category": {"id": m.category.id, "name": m.category.name} if m.category else None,
        "strength": m.strength,
        "dosageForm": m.dosage_form,
        "unit": m.unit,
        "rxClass": m.rx_class,
        "priceCentavos": m.price_centavos,
        "reorderLevel": m.reorder_level,
        "status": m.status,
        "notes": m.notes,
        "onHand": stock,
        "available": available,
        "updatedAt": iso(m.updated_at),
    }


def _check_links(db: DB, brand_id: str | None, category_id: str | None) -> None:
    if brand_id is not None and db.get(Brand, brand_id) is None:
        raise field_error("brandId", "Pick a brand from the list.")
    if category_id is not None and db.get(Category, category_id) is None:
        raise field_error("categoryId", "Pick a category from the list.")


def _code_taken(db: DB, code: str, but: str | None = None) -> bool:
    q = select(Medicine.id).where(func.lower(Medicine.code) == code.lower())
    if but:
        q = q.where(Medicine.id != but)
    return db.scalar(q) is not None


def missing_a_price():
    """On sale at no price: a sale is priced straight from the medicine, so it would go for nothing."""
    return (Medicine.status == "active") & (Medicine.price_centavos == 0)


@router.get("")
def list_medicines(
    _: Can("medicines.view"),
    db: DB,
    settings: SettingsDep,
    q: str | None = Query(None, max_length=80),
    state: Status | Literal["all"] = "active",
    category_id: str | None = Query(None, alias="categoryId", max_length=36),
    brand_id: str | None = Query(None, alias="brandId", max_length=36),
    rx_class: RxClass | None = Query(None, alias="rxClass"),
    missing: bool = Query(False, description="only medicines on sale with no price"),
) -> list[dict]:
    query = select(Medicine).order_by(func.lower(Medicine.generic_name), Medicine.strength)
    if missing:
        query = query.where(missing_a_price())
    if state != "all":
        query = query.where(Medicine.status == state)
    if category_id:
        query = query.where(Medicine.category_id == category_id)
    if brand_id:
        query = query.where(Medicine.brand_id == brand_id)
    if rx_class:
        query = query.where(Medicine.rx_class == rx_class)
    if q:
        like = f"%{q.lower()}%"
        query = query.outerjoin(Brand, Medicine.brand_id == Brand.id).where(
            or_(func.lower(Medicine.generic_name).like(like), func.lower(Medicine.code).like(like), func.lower(Brand.name).like(like))
        )
    medicines = list(db.scalars(query).unique())
    ids = [m.id for m in medicines]
    stock, available = on_hand(db, ids), sellable(db, ids, today(settings))
    return [medicine_out(m, stock.get(m.id, 0), available.get(m.id, 0)) for m in medicines]


@router.get("/reference")
def reference(_: Can("medicines.view"), db: DB) -> dict:
    """What a medicine form picks from."""
    return {
        "categories": [category_out(c) for c in db.scalars(select(Category).order_by(func.lower(Category.name)))],
        "brands": [brand_out(b) for b in db.scalars(select(Brand).order_by(func.lower(Brand.name)))],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_medicine(access: Can("medicines.create"), db: DB, body: MedicineIn) -> dict:
    if _code_taken(db, body.code):
        raise field_error("code", "Another medicine already has this code.")
    _check_links(db, body.brand_id, body.category_id)
    m = Medicine(**body.model_dump())
    db.add(m)
    db.flush()
    audit(db, access.user, "medicine.created", target=f"{m.code} {m.generic_name}", target_type="medicine", target_id=m.id)
    db.commit()
    db.refresh(m)
    return medicine_out(m, 0, 0)


@router.get("/{medicine_id}")
def read_medicine(_: Can("medicines.view"), db: DB, settings: SettingsDep, medicine_id: str) -> dict:
    m = get_or_404(db, Medicine, medicine_id, "medicine")
    on = today(settings)
    batches = db.scalars(select(Batch).where(Batch.medicine_id == m.id).order_by(Batch.expires_on))
    return {
        **medicine_out(m, on_hand(db, [m.id]).get(m.id, 0), sellable(db, [m.id], on).get(m.id, 0)),
        "batches": [
            {
                "id": b.id,
                "lotNo": b.lot_no,
                "expiresOn": day(b.expires_on),
                "qtyOnHand": b.qty_on_hand,
                "qtyReceived": b.qty_received,
                "status": b.status,
                "expired": b.expires_on <= on,
                "supplier": b.supplier.name if b.supplier else None,
            }
            for b in batches
        ],
    }


@router.patch("/{medicine_id}")
def update_medicine(access: Can("medicines.edit"), db: DB, settings: SettingsDep, medicine_id: str, body: MedicinePatch) -> dict:
    m = get_or_404(db, Medicine, medicine_id, "medicine")
    wanted = changed(body)
    for key in REQUIRED:
        if key in wanted and wanted[key] is None:
            raise field_error(camel([key])[0], "This can't be empty.")
    if "code" in wanted and _code_taken(db, wanted["code"], but=m.id):
        raise field_error("code", "Another medicine already has this code.")
    _check_links(db, wanted.get("brand_id"), wanted.get("category_id"))
    fields = [k for k, v in wanted.items() if getattr(m, k) != v]
    for k in fields:
        setattr(m, k, wanted[k])
    if fields:
        action = "medicine.status_changed" if fields == ["status"] else "medicine.updated"
        audit(db, access.user, action, target=f"{m.code} {m.generic_name}", target_type="medicine", target_id=m.id, fields=camel(fields))
        db.commit()
        db.refresh(m)
    return read_medicine(access, db, settings, m.id)


@router.delete("/{medicine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medicine(access: Can("medicines.delete"), db: DB, medicine_id: str) -> Response:
    """Only a medicine nothing refers to: once stocked, prescribed or sold it is
    history, and is discontinued instead."""
    m = get_or_404(db, Medicine, medicine_id, "medicine")
    used = any(
        db.scalar(select(func.count()).select_from(model).where(model.medicine_id == m.id))
        for model in (Batch, PrescriptionItem, SaleLine)
    )
    if used:
        raise conflict("This medicine has stock, prescriptions or sales on record. Mark it discontinued instead.")
    audit(db, access.user, "medicine.deleted", target=f"{m.code} {m.generic_name}", target_type="medicine", target_id=m.id)
    db.delete(m)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("This medicine is still in use. Mark it discontinued instead.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
