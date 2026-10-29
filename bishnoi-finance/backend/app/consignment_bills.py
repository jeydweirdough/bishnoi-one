"""Consignment bills (feature plan step 15d, finished 2026-10-29): what sold from a vendor's consignment, settled in
Inventory (event consignment.billed), becomes a draft vendor bill here, waiting for the vendor's own invoice
number and the usual approval.

- The vendor is found by TIN, else by name; one not in Finance yet is added (Inventory's name and TIN).
- One line per item, to the cost of goods sold account (the goods never were ours: sold straight from the
  vendor's stock), else the inventory account; VAT as the vendor is registered, its usual withholding.
- Once per settlement: the bill's number is the settlement's (CS-…) until Finance enters the vendor's.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.ledger import settings as posting_settings
from app.models import Bill, Supplier
from app.payables import work_out

ACTOR = "Bishnoi One"


def vendor_for(db: Session, data: dict) -> Supplier:
    v = data.get("supplier") or {}
    tin = "".join(ch for ch in str(v.get("tin") or "") if ch.isdigit())
    if len(tin) >= 9:
        formatted = f"{tin[:3]}-{tin[3:6]}-{tin[6:9]}"
        found = db.scalar(select(Supplier).where(Supplier.tin == formatted))
        if found is not None:
            return found
    name = str(v.get("name") or "Vendor").strip()[:200]
    found = db.scalar(select(Supplier).where(func.lower(Supplier.name) == name.lower()))
    if found is not None:
        return found
    s = Supplier(name=name, tin=f"{tin[:3]}-{tin[3:6]}-{tin[6:9]}" if len(tin) >= 9 else None, email=v.get("email"), created_by=ACTOR,
                 notes=f"Added from Inventory's consignment settlement {data.get('number')} (vendor {v.get('code')}).")
    db.add(s)
    db.flush()
    audit(db, ACTOR, "supplier.created", target=s.name, target_type="supplier", target_id=s.id, fields=["from a consignment settlement"])
    return s


def from_settlement(db: Session, data: dict, slug: str | None) -> Bill | None:
    from app.business_events import _state
    from app.routers.funds import today

    number = str(data.get("number") or "")[:60]
    if not number or not data.get("lines"):
        return None
    if db.scalar(select(Bill).where(Bill.bill_number == number, Bill.status != "void")) is not None:
        return None  # heard before
    vendor = vendor_for(db, data)
    ledger = posting_settings(db)
    account = ledger.cogs_account_id or ledger.inventory_account_id
    lines = [{"accountId": account, "description": f"Consignment sold: {line['name']} ({line['sku']}) × {line['quantity']}"[:200],
              "amountCentavos": int(line["total"]), "vat": "vat" if vendor.vat_registered else "none", "withholding": vendor.withholding}
             for line in data["lines"] if int(line.get("total") or 0) > 0]
    if not lines:
        return None
    settings = _state.get("settings")
    on = today(settings) if settings is not None else __import__("datetime").date.today()
    b = Bill(created_by=f"{ACTOR} (from {number})", supplier_id=vendor.id, bill_number=number, bill_date=on, due_date=on + timedelta(days=vendor.terms_days),
             amounts_include_vat=True, lines=lines,
             notes=(f"Consignment sales settled in Inventory ({number}). Enter the vendor's own invoice number when it comes."
                    + ("" if account else " Set the cost of goods sold account under Accounting, then pick it on each line."))[:500])
    w = work_out(db, lines, on, True)
    b.net_centavos, b.vat_centavos, b.withheld_centavos, b.total_centavos, b.payable_centavos = w.net, w.vat, w.withheld, w.total, w.payable
    db.add(b)
    db.flush()
    audit(db, ACTOR, "bill.created", target=f"{vendor.name} {number}", target_type="bill", target_id=b.id, fields=["from a consignment settlement"])
    return b
