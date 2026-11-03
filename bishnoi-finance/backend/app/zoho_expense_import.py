"""Zoho expenses, imported as read-only history (approved 2026-10-31, Plans/Plan - Q1 imports per area).

Not petty cash: an imported expense has no receipt file, and petty cash's rule that every receipt has one stays
as it is. It's a separate record (ImportedExpense) that nobody adds or edits by hand; new spending still uses
petty cash or bills. It posts as a petty cash voucher does (Dr accounts and Input VAT, Cr the money account and
tax withheld) and reaches the purchase lists through app/bir_reports.py. A mistake is voided, reversing its entry.

A company comes only from its label's confirmed match (CF.Cost Centre is not a company field by itself). Tax is
kept only when Finance's working-out equals Zoho's. Withholding counts only when the export states it, with an
ATC Finance knows and the amount Finance works out; today's exports have no withholding column at all.
"""
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.audit import audit
from app.import_review import ISSUES
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.locks import begin_change, lock_series
from app.models import Account, ImportedExpense, ImportedExpenseLine, ImportLink, ImportRun
from app.payables import PURCHASE_TYPES, VAT_KINDS, WITHHOLDING, work_out
from app.zoho_import import (SOURCE, account_key, closed_on, companies_from, created_records, fingerprint, gap, links_by_source, money_key, peso, pick,
                             posting_accounts, read_pack, record, rows_out, saved, summary, tax_key)

SAID = {"unsupported_components": "It's marked reimbursable, or has an amount Finance's imported expense has no place for yet."}
# Zoho's CF.Type against the purchase type chosen: only a plain contradiction holds it. "Rental" says neither.
SERVICE, GOODS = {"services"}, {"other_goods", "capital_goods", "importation"}


def plan(db, docs: list[dict], settings) -> list[dict]:
    from app.routers.funds import today
    from app.routers.vouchers import paying_accounts

    every = saved(db)
    matches = {k: m for k, m in every.items() if m.status == "confirmed"}
    companies_from(matches, docs)
    done = created_records(db, "expense")
    links = links_by_source(db, "expense")
    usable, s = posting_accounts(db), posting_settings(db)
    money = {a.id for a in paying_accounts(db)}
    known = {r for (r,) in db.execute(select(ImportedExpense.source_id).where(ImportedExpense.source == SOURCE))}
    out = []
    for d in docs:
        row = {"kind": "expense", "sourceId": d["sourceId"], "number": d["number"], "party": d["party"], "date": d["date"], "total": d["total"],
               "company": d["company"], "reasons": [], "outcome": "ready", "expense": None}
        out.append(row)
        if d["sourceId"] in done:
            link = links.get(d["sourceId"])
            row.update(outcome="imported", expenseId=link.expense_id if link else None)
            continue
        if d["company"] == "gpi":
            row.update(outcome="skipped", reasons=["Company label confirmed as GPI: not 2MG's expense."])
            continue
        reasons = row["reasons"]
        if d["company"] != "2mg":
            reasons.append(f"Company label “{d['companySource'] or 'none'}” isn't confirmed yet (Settings → Import matching).")
        reasons += [SAID.get(c, ISSUES[c]) for c in d["issues"]]
        if d["sourceId"] in known:
            reasons.append("This Zoho expense is already in Finance.")
        if len(d["sourceId"]) > 120 or len(d["number"]) > 60 or len(d["original"]["reference"]) > 80 or len(d["original"]["voucher"]) > 80 or len(d["original"]["department"]) > 120 or len(d["original"]["pic"]) > 120:
            reasons.append("A Zoho ID, number or reference is longer than Finance keeps; it was not shortened.")
        if d["date"] > today(settings).isoformat():
            reasons.append("The expense date is in the future.")
        if closed := closed_on(s, d["date"]):
            reasons.append(closed)
        inclusive = d["original"]["inclusiveTax"]
        if inclusive not in ("true", "false") or len({ln["inclusive"] for ln in d["lines"]}) > 1:
            reasons.append("The export doesn't say clearly whether the amounts include tax.")
        if not d["party"] and d["tax"]:
            reasons.append("It claims input VAT, but the export names no vendor; the purchase lists need one.")
        m = matches.get(money_key(d, "paid_through"))
        if m is None or m.account_id is None:
            reasons.append(f"Paid-through account “{d['original']['moneyAccount'] or 'none'}” isn't matched and confirmed yet.")
        elif m.account_id not in money:
            reasons.append("The paid-through account is matched to an account outside CASH.")
        lines = []
        for i, ln in enumerate(d["lines"], 1):
            a, t = every.get(account_key(ln, "expense")), every.get(tax_key(ln, "expense"))
            label, tax_label = ln["account"] or "no account", ln["taxName"] or "blank"
            account_id, _, changed_a = pick(a, d, i, ln, "account_id")
            purchase, _, changed_p = pick(a, d, i, ln, "purchase_type")
            vat, _, changed_t = pick(t, d, i, ln, "vat_kind")
            if account_id is None:
                reasons.append(gap(a, "Expense account", label, changed_a))
            elif account_id not in usable:
                reasons.append(f"Expense account “{label}” is matched to an account an expense can't use (active expense or asset accounts).")
            if account_id is not None and purchase not in PURCHASE_TYPES:
                reasons.append(gap(a, "Expense account", label, changed_p) if changed_p else f"“{label}” has no purchase type confirmed.")
            if vat not in VAT_KINDS:
                reasons.append(gap(t, "Tax label", tax_label, changed_t))
            said = ln["sourceType"].casefold()
            if purchase in PURCHASE_TYPES and ((said == "services" and purchase not in SERVICE) or (said == "goods" and purchase not in GOODS)):
                reasons.append(f"Zoho says {ln['sourceType']}, but “{label}” takes {PURCHASE_TYPES[purchase]}. Choose for this record on Import matching.")
            code = None
            if ln["tdsAmount"]:
                code = ln["tdsName"].strip().upper()
                if code not in WITHHOLDING:
                    reasons.append("Tax was withheld, but the export doesn't state an ATC Finance knows.")
            if account_id in usable and purchase in PURCHASE_TYPES and vat in VAT_KINDS and (not ln["tdsAmount"] or code in WITHHOLDING):
                lines.append({"accountId": account_id, "description": (ln["description"] or None) and ln["description"][:200],
                              "amountCentavos": ln.get("sourceGross", ln["amount"]) if inclusive == "true" else ln["amount"],
                              "vat": vat, "withholding": code, "purchaseType": purchase, "sourceAccount": ln["account"][:200], "sourceTax": ln["taxName"][:100]})
        reasons[:] = list(dict.fromkeys(reasons))
        if not reasons and len(lines) == len(d["lines"]):
            w = work_out(db, lines, date.fromisoformat(d["date"]), inclusive == "true")
            if w.total != d["total"] or w.vat != d["tax"]:
                reasons.append(f"Finance works this expense out as {peso(w.total)} with {peso(w.vat)} VAT; Zoho shows {peso(d['total'])} with {peso(d['tax'])} VAT.")
            stated = sum(ln["tdsAmount"] for ln in d["lines"])
            if w.withheld != stated:
                reasons.append(f"Finance works out {peso(w.withheld)} withheld; Zoho shows {peso(stated)}.")
            if w.vat and not s.input_tax_account_id:
                reasons.append("The Input VAT default account isn't set (Accounting → Default accounts).")
            if w.withheld and not s.withholding_account_id:
                reasons.append("The withholding tax default account isn't set (Accounting → Default accounts).")
            row["expense"] = {"worked": w, "include": inclusive == "true", "paidFrom": m.account_id, "doc": d}
            row["choices"] = [m.account_id, [[ln["accountId"], ln["purchaseType"], ln["vat"], ln["withholding"]] for ln in lines]]
        if reasons:
            row.update(outcome="held", expense=None)
    return out


def preview(db, settings, files: list[dict]) -> dict:
    rows = plan(db, read_pack(files, "expenses"), settings)
    return {**summary(rows, source_fingerprint=fingerprint(files)), "rows": rows_out(rows)}


def post_expense(db, x: ImportedExpense, w, who: str, by_id: str):
    s = posting_settings(db)
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_({ln["accountId"] for ln in w.lines})))}
    place = ", ".join(p for p in (x.vendor, x.reference) if p) or f"entry {x.number}"
    legs = [Leg(accounts[ln["accountId"]], debit=ln["netCentavos"], description=f"{place}"[:200]) for ln in w.lines]
    legs.append(Leg(db.get(Account, s.input_tax_account_id) if s.input_tax_account_id else None, debit=w.vat, description="Input VAT"))
    legs.append(Leg(x.paid_from, credit=w.payable, description=f"Imported expense {x.number}"[:200]))
    legs.append(Leg(db.get(Account, s.withholding_account_id) if s.withholding_account_id else None, credit=w.withheld, description="Tax withheld (EWT)"))
    return post(db, x.expense_date, f"Imported expense {x.number} ({place})"[:300], legs, who, reference=(x.reference or x.number)[:80], source="expense", by_id=by_id)


def import_expenses(db, settings, user, files: list[dict], plan_key: str) -> dict:
    begin_change(db)
    lock_series(db, "import:zoho")  # one import at a time (PostgreSQL; SQLite's write lock already does it)
    rows = plan(db, read_pack(files, "expenses"), settings)
    result = summary(rows, source_fingerprint=fingerprint(files))
    if result["planKey"] != plan_key:
        raise HTTPException(409, "The source files, matches or expenses changed since the preview. Preview again, then import.")
    run = ImportRun(kind="expenses", files=[f["name"] for f in files], fingerprint=fingerprint(files), counts=result["counts"],
                    created_by=user.full_name[:120], created_by_id=user.id)
    db.add(run); db.flush()
    who = f"{user.full_name} (Zoho import)"[:120]
    now = datetime.now(UTC)
    for row in rows:
        if row["outcome"] == "imported":
            continue
        rec = record(db, run, "expense", row, created=row["outcome"] == "ready")
        if row["outcome"] != "ready":
            continue
        p, w = row["expense"], row["expense"]["worked"]
        d, o = p["doc"], p["doc"]["original"]
        x = ImportedExpense(source=SOURCE, source_id=row["sourceId"], number=row["number"], reference=o["reference"] or None, voucher=o["voucher"] or None,
                            department=o["department"] or None, person_in_charge=o["pic"] or None, status="posted", expense_date=date.fromisoformat(row["date"]),
                            vendor=row["party"], paid_from_id=p["paidFrom"], amounts_include_vat=p["include"], net_centavos=w.net, vat_centavos=w.vat,
                            withheld_centavos=w.withheld, total_centavos=w.total, paid_out_centavos=w.payable, run_id=run.id, source_file=files[0]["name"][:200],
                            imported_by=who, imported_by_id=user.id, imported_at=now)
        x.lines = [ImportedExpenseLine(position=i, account_id=ln["accountId"], source_account=ln["sourceAccount"], source_tax=ln["sourceTax"], description=ln["description"],
                                       purchase_type=ln["purchaseType"], vat=ln["vat"], withholding=ln["withholding"], amount_centavos=ln["amountCentavos"],
                                       net_centavos=ln["netCentavos"], vat_centavos=ln["vatCentavos"], withheld_centavos=ln["withheldCentavos"])
                   for i, ln in enumerate(w.lines, 1)]
        db.add(x); db.flush()
        db.refresh(x, ["paid_from"])
        x.entry_id = post_expense(db, x, w, who, user.id).id
        db.add(ImportLink(record_id=rec.id, expense_id=x.id))
        audit(db, user, "expense.imported", target=f"{x.number} {x.vendor}"[:200], target_type="imported_expense", target_id=x.id)
        row["expenseId"] = x.id
    audit(db, user, "imports.expenses", target=f"{result['counts']['ready']} expenses", target_type="import", target_id=run.id)
    db.commit()
    return {"runId": run.id, **result, "rows": rows_out(rows)}

