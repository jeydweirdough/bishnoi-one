"""What an administrator can clean up in Pharmacy (app/recycle_bin.py, 2026-10-30). People and roles aren't
here: they're kept on the Platform (Admin Console → People).

A sale or a dispensing took medicine off its batches: deleting one goes with its stock movements and puts
the quantities back on the batches; restoring takes them off again."""

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Batch
from app.recycle_bin import Kind

P = "nbph_"


def _lines(db: Session, rows: list[tuple[str, dict]], sign: int) -> None:
    for table, r in rows:
        if table in (P + "sale_lines", P + "dispensing_lines") and r.get("batch_id") and r.get("quantity"):
            db.execute(update(Batch).where(Batch.id == r["batch_id"]).values(qty_on_hand=Batch.qty_on_hand + sign * int(r["quantity"])))


def movements(db: Session, row: dict) -> list[tuple[str, str, object]]:
    return [(P + "stock_movements", "reference", row["number"])] if row.get("number") else []


posted_doc = {"posted": lambda r: True, "extra": movements, "on_delete": lambda db, rows: _lines(db, rows, +1),
              "on_restore": lambda db, rows: _lines(db, rows, -1), "tables_named": {P + "stock_movements": "stock movements"}}

KINDS: list[Kind] = [
    Kind("sales", "Sales", P + "sales", "number", owns=(P + "sale_lines",), search=("number",), sub="payment_method", **posted_doc),
    Kind("dispensings", "Dispensings", P + "dispensings", "number", owns=(P + "dispensing_lines",), search=("number",), **posted_doc),
    Kind("returns", "Returns", P + "returns", "number", search=("number", "reason"), posted=lambda r: True),
    Kind("prescriptions", "Prescriptions", P + "prescriptions", "number", owns=(P + "prescription_items",), search=("number", "prescriber_name"), sub="status"),
    Kind("patients", "Patients", P + "patients", "full_name", search=("full_name", "phone", "email")),
    Kind("receivings", "Receivings", P + "receivings", "number", search=("number", "reference")),
    Kind("material-reviews", "Material reviews", P + "material_reviews", "title", search=("title", "number"), sub="status"),
    Kind("medicines", "Medicines", P + "medicines", "generic_name", group="Set-up", owns=(P + "batches",), search=("generic_name", "code"), sub="code"),
    Kind("batches", "Batches", P + "batches", lambda r: r.get("lot_no") or r.get("id"), group="Set-up", search=("lot_no",), sub="status"),
    Kind("suppliers", "Suppliers", P + "suppliers", "name", group="Set-up", search=("name",)),
    Kind("categories", "Categories", P + "categories", "name", group="Set-up", search=("name",)),
    Kind("brands", "Brands", P + "brands", "name", group="Set-up", search=("name",)),
]
