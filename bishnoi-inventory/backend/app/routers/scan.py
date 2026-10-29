"""Barcode and QR scanning (feature plan step 14c, 2026-10-29): what a scanned code is, in one lookup, and
counting by scanning. A scanner that types like a keyboard and a phone's camera both end up here.

    GET  /inventory/scan?code=                  what it is: an item (barcode or SKU), a batch, a serial number,
                                                or a document (DR-, SO-, PO-, RC-, CNT-, QC-, ADJ-, TR-…)
    POST /inventory/counts/{id}/scan            one more counted (or `quantity`) on the count's line for it
"""

from fastapi import APIRouter, Query
from pydantic import Field
from sqlalchemy import func, select

from app.access import allowed
from app.api import Api, conflict, field_error
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Adjustment, Batch, Count, CountLine, Location, Order, Packaging, Product, PurchaseOrder, QualityCheck, Receipt, SalesOrder, Serial, Transfer
from app.out import product_ref

router = APIRouter(prefix="/inventory", tags=["scanning"])

# Each document kind: its model, the page it opens in the one app, and what it's called.
DOCUMENTS = (
    (Order, "/inventory/orders/", "Delivery"),
    (SalesOrder, "/sales/orders/", "Sales order"),
    (PurchaseOrder, "/inventory/purchase-orders/", "Purchase order"),
    (Receipt, "/inventory/receipts/", "Purchase receive"),
    (Count, "/inventory/counts/", "Inventory count"),
    (QualityCheck, "/inventory/quality-checks/", "Quality check"),
    (Adjustment, "/inventory/adjustments/", "Adjustment"),
    (Transfer, "/inventory/transfers/", "Transfer order"),
)


def clean(code: str) -> str:
    return code.strip().strip("\x00").strip()


def product_by_code(db, code: str) -> Product | None:
    low = code.lower()
    return db.scalar(select(Product).where(func.lower(Product.barcode) == low)) or db.scalar(select(Product).where(func.lower(Product.sku) == low))


def identify(db, code: str) -> dict:
    """What a scanned code is; {"kind": "unknown"} when nothing matches."""
    code = clean(code)
    if not code:
        return {"kind": "unknown", "code": code}
    product = product_by_code(db, code)
    if product is not None:
        return {"kind": "product", "code": code, "product": product_ref(product), "href": f"/inventory/products/{product.id}"}
    # A pack's own barcode (step 14e): the item, and how many of it the pack holds.
    pack = db.scalar(select(Packaging).where(func.lower(Packaging.barcode) == code.lower()))
    if pack is not None:
        item = db.get(Product, pack.product_id)
        return {"kind": "product", "code": code, "product": product_ref(item), "pack": {"name": pack.name, "quantity": pack.quantity},
                "href": f"/inventory/products/{item.id}"}
    low = code.lower()
    batches = db.scalars(select(Batch).where(func.lower(Batch.batch_no) == low).limit(5)).all()
    if len(batches) == 1:
        b = batches[0]
        return {"kind": "batch", "code": code, "product": product_ref(b.product), "batch": {"id": b.id, "batchNo": b.batch_no,
                "expiresOn": b.expires_on.isoformat() if b.expires_on else None}, "href": f"/inventory/products/{b.product_id}/batches"}
    serial = db.scalar(select(Serial).where(func.lower(Serial.serial_no) == low))
    if serial is not None:
        return {"kind": "serial", "code": code, "product": product_ref(db.get(Product, serial.product_id)), "serial": serial.serial_no,
                "batchId": serial.batch_id, "href": f"/inventory/serials?q={serial.serial_no}"}
    for model, path, label in DOCUMENTS:
        doc = db.scalar(select(model).where(func.lower(model.number) == low))
        if doc is not None:
            return {"kind": "document", "code": code, "document": {"id": doc.id, "number": doc.number, "label": label}, "href": f"{path}{doc.id}"}
    if len(batches) > 1:  # the same batch number on several items: say which
        return {"kind": "batches", "code": code, "batches": [{"id": b.id, "batchNo": b.batch_no, "product": product_ref(b.product)} for b in batches]}
    return {"kind": "unknown", "code": code}


@router.get("/scan")
def scan(_: CurrentUser, db: DB, code: str = Query(min_length=1, max_length=120)) -> dict:
    return identify(db, code)


class CountScanIn(Api):
    code: str = Field(min_length=1, max_length=120)
    quantity: int = Field(1, ge=1, le=100000)


@router.post("/counts/{count_id}/scan")
def count_by_scan(_: allowed("counts.create"), me: CurrentUser, db: DB, count_id: str, body: CountScanIn) -> dict:
    """Adds what was scanned to the count: the item (by barcode or SKU) or its batch (by batch number). Several
    counters can scan into one count: each scan adds, nobody overwrites another's."""
    c = db.get(Count, count_id)
    if c is None:
        raise field_error("code", "That count doesn't exist.")
    if c.status != "open":
        raise conflict(f"{c.number} is {c.status}: reopen it to count more.")
    what = identify(db, body.code)
    if what["kind"] not in ("product", "batch"):
        raise field_error("code", "That isn't an item or a batch: scan the item's barcode or its batch number." if what["kind"] != "unknown"
                          else f"Nothing has the code {what['code']}.")
    product_id = what["product"]["id"]
    batch_id = what.get("batch", {}).get("id") if what["kind"] == "batch" else None
    lines = [line for line in c.lines if line.product_id == product_id and (batch_id is None or line.batch_id == batch_id)]
    if not lines:
        product = db.get(Product, product_id)
        if product.track_batches and batch_id is None:
            raise field_error("code", f"{product.name} is tracked by batch and isn't expected here: scan its batch number.")
        default = db.scalar(select(Location).where(Location.warehouse_id == c.warehouse_id, Location.is_default))
        if default is None:
            raise conflict("This warehouse has no default location for items found that weren't expected.")
        line = CountLine(position=len(c.lines), product_id=product_id, location_id=default.id, batch_id=batch_id, expected=0, counted=0)
        c.lines.append(line)
        lines = [line]
        found_new = True
    else:
        found_new = False
    # More than one line for the item (several locations or batches): the first not yet counted, else the first.
    line = next((x for x in lines if x.counted is None), lines[0])
    # A pack scanned counts everything in it (step 14e).
    line.counted = (line.counted or 0) + body.quantity * (what.get("pack") or {}).get("quantity", 1)
    if found_new:
        audit(db, me, "count.line_added", target=c.number, target_type="count", target_id=c.id, fields=["scanned"])
    db.commit()
    return {"lineId": line.id, "product": what["product"], "batch": what.get("batch"), "pack": what.get("pack"), "counted": line.counted, "expected": line.expected, "new": found_new,
            "otherLines": len(lines) - 1}
