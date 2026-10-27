"""Brings Zoho's vendors in as suppliers (2026-10-27), from the reviewed file that
scripts/zoho_vendors.py makes: only the rows whose kind is `supplier` (the ones
the company buys products from; Finance takes the rest).

    uv run python -m app.tools.import_vendors <review.csv> --company getmeds [--to "<database url>"] [--dry-run]
    uv run python -m app.tools.import_vendors <review.csv> --company getmeds --remove-demo

Each supplier's code is its Zoho number (GC000761), so running it again updates
them instead of adding them twice; what someone changed here since isn't
overwritten with blanks. --to is the app's database (DATABASE_URL when not
given); the company's own is used, as the app does (neondb -> neondb_getmeds).
--remove-demo also removes the demo suppliers (ABC, PHX, VIS) when nothing uses them.
"""

import argparse
import csv
import sys

from sqlalchemy import func, select

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Product, PurchaseOrder, Supplier, SupplierProduct
from app.tenants import database_url

DEMO = ("ABC", "PHX", "VIS")
WHO = "Zoho vendors import"


def values(row: dict) -> dict:
    tin = row["tin"] and (f"{row['tin']}-{row['branch_code']}" if row["branch_code"] else row["tin"])
    notes = []
    if row["company_name"] and row["company_name"].lower() != row["name"].lower():
        notes.append(f"Registered name: {row['company_name']}")
    if row["website"]:
        notes.append(f"Website: {row['website']}")
    if row["ewt"]:
        notes.append("Tax is withheld from its payments (EWT): set its usual ATC.")
    if row["merged_zoho_ids"]:
        notes.append(f"Also in Zoho as {row['merged_zoho_ids']}.")
    return {
        "name": row["name"][:160],
        "contact_person": (row["contact_person"] or None) and row["contact_person"][:120],
        "email": row["email"] or None,
        "phone": (row["phone"] or row["mobile"] or None),
        "address": row["address"] or None,
        "notes": "\n".join(notes) or None,
        "is_active": row["active"] == "yes",
        "tin": tin or None,
        "vat_status": "non_vat" if row["vat"] == "non_vat" else "vat",
        "currency": row["currency"] or "PHP",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("file")
    p.add_argument("--company", required=True)
    p.add_argument("--to", help="the app's database (DATABASE_URL when not given)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--remove-demo", action="store_true")
    args = p.parse_args()

    rows = [r for r in csv.DictReader(open(args.file, encoding="utf-8-sig", newline="")) if r["kind"].strip().lower() == "supplier"]
    url = database_url(args.to or get_settings().database_url, args.company)
    engine = make_engine(url)
    upgrade(engine)
    added = changed = 0
    with make_sessions(engine)() as db:
        for row in rows:
            code = row["zoho_id"].strip().upper()
            new = values(row)
            s = db.scalar(select(Supplier).where(func.lower(Supplier.code) == code.lower()))
            if s is None:
                s = Supplier(code=code, **new)
                db.add(s)
                db.flush()
                audit(db, WHO, "supplier.created", target=s.name, target_type="supplier", target_id=s.id)
                added += 1
                continue
            # Only what Zoho says and this side doesn't: nothing typed here is blanked.
            fields = [k for k, v in new.items() if v not in (None, "") and getattr(s, k) in (None, "") or k in ("is_active", "vat_status", "currency") and getattr(s, k) != v]
            for k in fields:
                setattr(s, k, new[k])
            if fields:
                audit(db, WHO, "supplier.updated", target=s.name, target_type="supplier", target_id=s.id, fields=fields)
                changed += 1

        removed = []
        if args.remove_demo:
            for code in DEMO:
                s = db.scalar(select(Supplier).where(Supplier.code == code))
                if s is None:
                    continue
                used = any(
                    db.scalar(select(func.count()).select_from(t).where(t.supplier_id == s.id))
                    for t in (PurchaseOrder, Product, SupplierProduct)
                )
                if used:
                    print(f"  kept demo supplier {code}: something uses it")
                    continue
                audit(db, WHO, "supplier.deleted", target=s.name, target_type="supplier", target_id=s.id)
                db.delete(s)
                removed.append(code)

        print(f"{url.split('@')[-1].split('?')[0]}: {added} added, {changed} updated, {len(rows) - added - changed} unchanged; demo removed: {removed or 'none'}")
        if args.dry_run:
            db.rollback()
            print("Dry run: nothing saved.")
        else:
            db.commit()


if __name__ == "__main__":
    sys.exit(main())
