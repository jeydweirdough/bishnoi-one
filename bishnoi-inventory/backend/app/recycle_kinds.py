"""What an administrator can clean up in Inventory (app/recycle_bin.py, 2026-10-30). People and roles aren't
here: they're kept on the Platform (Admin Console → People).

Posted stock documents (a receipt, an issued delivery, an approved adjustment, a dispatched or received
transfer) go with their stock movements, and the stock balances are put back as they were before it: the
movements' changes taken off on delete, added back on restore."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Stock
from app.recycle_bin import Kind

P = "nbin_"


def movements_of(db: Session, row: dict) -> list[tuple[str, str, object]]:
    return [(P + "movements", "reference_id", row["id"])]


def _balance(db: Session, rows: list[tuple[str, dict]], sign: int) -> None:
    """Each taken movement's change on hand, taken off (sign -1) or put back (+1) its stock row."""
    for table, r in rows:
        if table != P + "movements" or not r.get("on_hand_change") or not r.get("location_id"):
            continue
        stock = db.scalar(select(Stock).where(Stock.product_id == r["product_id"], Stock.location_id == r["location_id"],
                                              Stock.batch_id.is_(None) if r.get("batch_id") is None else Stock.batch_id == r["batch_id"]))
        if stock is not None:
            db.execute(update(Stock).where(Stock.id == stock.id).values(on_hand=Stock.on_hand + sign * int(r["on_hand_change"])))


def off(db: Session, rows: list[tuple[str, dict]]) -> None:
    _balance(db, rows, -1)


def back(db: Session, rows: list[tuple[str, dict]]) -> None:
    _balance(db, rows, +1)


posted_doc = {"extra": movements_of, "on_delete": off, "on_restore": back, "tables_named": {P + "movements": "stock movements"}}

KINDS: list[Kind] = [
    # Records
    Kind("purchase-orders", "Purchase orders", P + "purchase_orders", "number", owns=(P + "purchase_order_lines",), search=("number",), sub="status"),
    Kind("receipts", "Receipts", P + "receipts", "number", owns=(P + "receipt_lines", P + "quality_checks", P + "quality_check_lines"), search=("number", "delivery_ref"),
         posted=lambda r: True, **posted_doc),
    Kind("sales-orders", "Sales orders", P + "sales_orders", "number", owns=(P + "sales_order_lines",), search=("number", "customer_name"), sub="customer_name"),
    Kind("deliveries", "Deliveries", P + "orders", "number", owns=(P + "order_lines", P + "packages", P + "package_lines"), search=("number", "recipient"), sub="status",
         posted=lambda r: r.get("status") in ("issued", "delivered"), **posted_doc),
    Kind("transfers", "Transfers", P + "transfers", "number", owns=(P + "transfer_lines",), search=("number",), sub="status",
         posted=lambda r: r.get("status") in ("dispatched", "in_transit", "received"), **posted_doc),
    Kind("adjustments", "Adjustments", P + "adjustments", "number", owns=(P + "adjustment_lines",), search=("number", "reason"), sub="status",
         posted=lambda r: r.get("status") == "approved", **posted_doc),
    Kind("counts", "Counts", P + "counts", "number", owns=(P + "count_lines",), search=("number",), sub="status"),
    Kind("waves", "Waves", P + "waves", "number", search=("number",), sub="status"),
    Kind("quality-checks", "Quality checks", P + "quality_checks", "number", owns=(P + "quality_check_lines",), search=("number",), sub="status"),
    Kind("consignment-settlements", "Consignment settlements", P + "consignment_settlements", "number", search=("number",)),
    # Set-up lists
    Kind("products", "Products", P + "products", "name", group="Set-up",
         owns=(P + "product_images", P + "product_documents", P + "product_packagings", P + "supplier_products", P + "stock", P + "batches", P + "serials"),
         search=("name", "sku"), sub="sku"),
    Kind("vendors", "Vendors", P + "suppliers", "name", group="Set-up", owns=(P + "supplier_products",), search=("name", "code"), sub="code"),
    Kind("warehouses", "Warehouses", P + "warehouses", "name", group="Set-up", owns=(P + "locations", P + "count_schedules"), search=("name", "code"), sub="code"),
    Kind("locations", "Locations", P + "locations", "name", group="Set-up", search=("name", "code"), sub="code"),
    Kind("categories", "Categories", P + "categories", "name", group="Set-up", search=("name",)),
    Kind("brands", "Brands", P + "brands", "name", group="Set-up", search=("name",)),
    Kind("units", "Units", P + "units", "name", group="Set-up", search=("name", "code"), sub="code"),
    Kind("couriers", "Couriers", P + "couriers", "name", group="Set-up", search=("name", "code")),
    Kind("operation-types", "Operation types", P + "operation_types", "name", group="Set-up", search=("name", "code")),
    Kind("count-schedules", "Count schedules", P + "count_schedules", "name", group="Set-up", search=("name",)),
]
