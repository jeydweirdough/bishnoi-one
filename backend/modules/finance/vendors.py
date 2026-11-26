"""Finance's suppliers are Inventory's vendors (owner, 2026-11-24: one vendor list, never typed twice).

Inventory owns who a vendor is: name, TIN, contact details, terms, active or not. Each change arrives as the event
vendor.saved and the linked Finance supplier follows it; the first time, the supplier with the same TIN or name is
linked, or one is added from the vendor. What is Finance's own stays Finance's: payables account, withholding, tax
defaults confirmed. On books that review suppliers (2MG's), a person confirms each link, so nothing is linked here."""

import re

from sqlalchemy.orm import Session

from modules.finance import company_scope
from modules.finance.audit import audit
from modules.finance.models import Supplier

ACTOR = "Inventory"


def _tin(raw) -> tuple[str | None, str | None]:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) < 9:
        return None, None
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]}", (digits[9:14] or None)


def _terms_days(raw) -> int | None:
    found = re.search(r"\d+", str(raw or ""))
    return int(found.group()) if found else (0 if str(raw or "").strip().upper() in {"COD", "CASH"} else None)


def saved(db: Session, data: dict, slug: str | None = None) -> Supplier | None:
    from modules.finance.purchase_intake import PurchaseSupplierLink
    from modules.finance.consignment_bills import vendor_for

    vendor_id = str(data.get("id") or "")
    if not vendor_id or not str(data.get("name") or "").strip():
        return None
    key = ("2mg", vendor_id)  # the link's company key: these books
    link = db.get(PurchaseSupplierLink, key)
    s = db.get(Supplier, link.supplier_id) if link else None
    if s is None:
        if company_scope.configured(db, "supplier"):
            return None  # 2MG's books: a person confirms the link on the received purchase
        s = vendor_for(db, {"supplier": {"name": data.get("name"), "tin": data.get("tin"), "email": data.get("email")}},
                       why=f"Inventory vendor {data.get('code') or ''}".strip() + ".")
        if link is None:
            db.add(PurchaseSupplierLink(company=key[0], source_supplier_id=vendor_id, supplier_id=s.id, reviewed_by=ACTOR,
                                        evidence="Same vendor in Inventory (matched by TIN or name, or added from it)."))
    tin, branch = _tin(data.get("tin"))
    wanted = {
        "name": str(data["name"]).strip()[:200],
        "email": data.get("email") or s.email,
        "phone": data.get("phone") or s.phone,
        "address": data.get("address") or s.address,
        "is_active": bool(data.get("isActive", True)),
    }
    if tin:
        wanted["tin"] = tin
        if branch:
            wanted["branch_code"] = branch
    if data.get("vatStatus") in ("vat", "non_vat"):
        wanted["vat_registered"] = data["vatStatus"] == "vat"
    days = _terms_days(data.get("paymentTerms"))
    if days is not None:
        wanted["terms_days"] = days
    fields = [k for k, v in wanted.items() if getattr(s, k, None) != v]
    for k in fields:
        setattr(s, k, wanted[k])
    db.flush()
    if fields:
        audit(db, ACTOR, "supplier.updated", target=s.name, target_type="supplier", target_id=s.id, fields=fields)
    return s
