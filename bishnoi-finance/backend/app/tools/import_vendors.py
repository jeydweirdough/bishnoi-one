"""Brings Zoho's vendors in as Finance's suppliers (2026-10-27), from the reviewed
file that scripts/zoho_vendors.py makes: every real vendor (kind `supplier` or
`payee`; `test` rows are left out), for bills, the tax withheld and the BIR's lists.

    uv run python -m app.tools.import_vendors <review.csv> [--to "<database url>"] [--dry-run]

A vendor already here (same name) is filled in, never blanked; the rest are added.
Product suppliers post to AP - Trade (2101-000) and the others to AP - Non-Trade
(2102-000) when the chart has them. Where Zoho says tax is withheld (EWT), the ATC
is left for Finance to choose: the note says so.
"""

import argparse
import csv
import sys

from sqlalchemy import func, select

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Account, Supplier

WHO = "Zoho vendors import"


def values(row: dict, accounts: dict[str, str]) -> dict:
    notes = [f"Zoho {row['zoho_id']}" + (f" (also {row['merged_zoho_ids']})" if row["merged_zoho_ids"] else "")]
    if row["ewt"]:
        notes.append("Tax is withheld (EWT): choose its ATC.")
    if row["currency"] and row["currency"] != "PHP":
        notes.append(f"Bills in {row['currency']}.")
    if row["website"]:
        notes.append(row["website"])
    company = row["company_name"] if row["company_name"].lower() != row["name"].lower() else ""
    return {
        "name": row["name"][:200],
        "company_name": company[:200] or None,
        "salutation": row["salutation"][:10] or None,
        "first_name": row["first_name"][:80] or None,
        "last_name": row["last_name"][:80] or None,
        "mobile": row["mobile"][:40] or None,
        "phone": row["phone"][:40] or None,
        "email": row["email"][:254] or None,
        "tin": row["tin"] or None,
        "branch_code": row["branch_code"] or None,
        "address": row["address"][:300] or None,
        "vat_registered": row["vat"] != "non_vat",
        "notes": " ".join(notes)[:500],
        "is_active": row["active"] == "yes",
        "payables_account_id": accounts.get("2101-000" if row["kind"] == "supplier" else "2102-000"),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("file")
    p.add_argument("--to", help="Finance's database (DATABASE_URL when not given)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    rows = [r for r in csv.DictReader(open(args.file, encoding="utf-8-sig", newline="")) if r["kind"].strip().lower() in ("supplier", "payee")]
    url = args.to or get_settings().database_url
    engine = make_engine(url)
    upgrade(engine)
    added = changed = 0
    with make_sessions(engine)() as db:
        accounts = {a.code: a.id for a in db.scalars(select(Account).where(Account.code.in_(("2101-000", "2102-000"))))}
        for row in rows:
            new = values(row, accounts)
            s = db.scalar(select(Supplier).where(func.lower(Supplier.name) == new["name"].lower()))
            if s is None:
                s = Supplier(created_by=WHO, **new)
                db.add(s)
                db.flush()
                audit(db, WHO, "supplier.created", target=s.name, target_type="supplier", target_id=s.id)
                added += 1
                continue
            fields = [k for k, v in new.items() if v not in (None, "") and getattr(s, k) in (None, "")]
            for k in fields:
                setattr(s, k, new[k])
            if fields:
                audit(db, WHO, "supplier.updated", target=s.name, target_type="supplier", target_id=s.id, fields=fields)
                changed += 1
        print(f"{url.split('@')[-1].split('?')[0]}: {added} added, {changed} filled in, {len(rows) - added - changed} unchanged; "
              f"payables accounts found: {sorted(accounts) or 'none (set each supplier's account by hand)'}")
        if args.dry_run:
            db.rollback()
            print("Dry run: nothing saved.")
        else:
            db.commit()


if __name__ == "__main__":
    sys.exit(main())
