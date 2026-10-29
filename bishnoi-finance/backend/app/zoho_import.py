"""Bills and supplier payments from Zoho Books exports into Finance (approved 2026-10-29).

Reads the files with the import review's parser (app/import_review.py) and uses only
*confirmed* import matches (ImportMatch). Imported bills and vouchers post exactly as ones
entered in Finance (the same accounts and entries), but:
- approvals are not replayed: they happened in Zoho, and the record says so;
- nothing is queued for sending to Zoho (these records came from Zoho);
- a Zoho record is created at most once (ImportRecord's unique index);
- anything not clearly supported is held with its reason, never guessed or forced.
"""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from app.audit import audit
from app.import_review import ISSUES, ReviewError, connect, norm, parse
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.locks import begin_change, lock_series, locked
from app.models import Account, Bill, ImportMatch, ImportRecord, ImportRun, PaymentVoucher, Supplier, VoucherLine
from app.payables import PURCHASE_TYPES, VAT_KINDS, work_out

SOURCE = "zoho"
COMPANIES = {"2mg": "2MG", "gpi": "GPI (Getmeds Philippines Inc.)"}
SECTIONS = ("company", "account", "tax", "money")
# What confirms each section: tax labels are confirmed by BIR and Compliance.
CONFIRMS = {"company": "imports.confirm", "account": "imports.confirm", "money": "imports.confirm", "tax": "imports.confirm_tax"}
WITHHOLDING_HELD = ("A Zoho supplier payment for this bill withheld tax. Where imported withholding goes "
                    "(on the bill line with its ATC, as Finance does, or with the payment) waits on Sir Mel.")
PAYMENT_WITHHOLDING_HELD = ("This payment withheld tax in Zoho. Where imported withholding goes (on the bill line with "
                            "its ATC, as Finance does, or with the payment) waits on Sir Mel.")


# Filled in without anyone choosing, because the answer is already known (changed 2026-10-29: the
# user asked for fewer approvals; filling these in by hand added nothing).
AUTOMATIC = "Automatic"
KNOWN_COMPANIES = {"2mg": "2mg", "getmeds": "gpi"}  # the user's answer, 2026-10-29 (Decisions)
COMPANY_NOTE = ("From the user's answer (2026-10-29): Zoho's “2MG” is 2MG, “Getmeds” is GPI. Zoho's tag can be wrong for "
                "a single bill: Cristal confirmed (2026-10-20) that when they disagree, Oojeema's company is right. Bills aren't checked one by one against Oojeema yet.")


class PackError(ValueError):
    pass


def read_pack(files: list[dict]) -> list[dict]:
    """The Zoho Bills export and the Vendor Payments export, together: a bill's payments tell
    whether tax was withheld on it, and a payment needs its bills."""
    try:
        docs, controls, manifests = parse(files)
    except ReviewError as error:
        raise PackError(str(error)) from None
    kinds = Counter(m["kind"] for m in manifests)
    if controls or set(kinds) != {"bill", "vendor_payment"} or any(n != 1 for n in kinds.values()):
        raise PackError("Choose two files together: the Zoho Bills export and the Zoho Vendor Payments export.")
    return docs


def fingerprint(files: list[dict]) -> str:
    h = hashlib.sha256()
    for f in sorted(files, key=lambda f: f["name"]):
        h.update(f["name"].encode()); h.update(b"\0"); h.update(f["content"].encode()); h.update(b"\0")
    return h.hexdigest()


# --- the keys a match is saved under ---------------------------------------------------------------

def company_key(d):
    return ("company", "bill", "", d["companySource"])


def account_key(ln):
    return ("account", "line", ln["accountCode"], ln["account"])


def tax_key(ln):
    return ("tax", "line", ln["taxRate"], ln["taxName"])


def money_key(d):
    return ("money", "paid_from", d["original"]["moneyCode"], d["original"]["moneyAccount"])


def match_key(m: ImportMatch):
    return (m.section, m.role, m.source_code, m.source_label)


def saved(db) -> dict:
    return {match_key(m): m for m in db.scalars(select(ImportMatch).where(ImportMatch.source == SOURCE))}


def confirmed(db) -> dict:
    return {k: m for k, m in saved(db).items() if m.status == "confirmed"}


def companies_from(matches: dict, docs: list[dict]) -> None:
    """A bill's company comes only from its label's confirmed match; then payments take theirs
    from their bills (the import review's connect)."""
    for d in docs:
        if d["kind"] == "bill":
            m = matches.get(company_key(d))
            d["company"] = m.company if m is not None and m.company in COMPANIES else "unconfirmed"
    connect(docs)


# --- loading an export: the groups to match ------------------------------------------------------

def load_groups(db, docs: list[dict], user) -> dict:
    """Saves each label the export uses (with how many records and how much), so people who
    didn't load the file see the same sheet. Lines of bills whose label is confirmed GPI are left
    out: they never come into 2MG's books."""
    companies_from(confirmed(db), docs)
    found = defaultdict(lambda: [0, 0])
    for d in docs:
        if d["kind"] == "bill":
            g = found[company_key(d)]; g[0] += 1; g[1] += d["total"]
            if d["company"] == "gpi":
                continue
            for ln in d["lines"]:
                for key in (account_key(ln), tax_key(ln)):
                    g = found[key]; g[0] += 1; g[1] += ln["amount"]
        elif d["kind"] == "vendor_payment" and d["company"] != "gpi":
            g = found[money_key(d)]; g[0] += 1; g[1] += d["total"]
    rows = saved(db)
    now = datetime.now(UTC)
    for key, (records, amount) in found.items():
        m = rows.get(key)
        if m is None:
            section, role, code, label = key
            if len(code) > 80 or len(label) > 200:
                raise PackError("A source label is longer than Finance keeps; it was not shortened. Check the export.")
            m = ImportMatch(source=SOURCE, section=section, role=role, source_code=code, source_label=label, status="open")
            db.add(m)
        m.records, m.amount_centavos, m.seen_at = records, amount, now
        if m.status == "open" and m.proposed_by is None:
            fill_in(db, m, now)
    # Labels the latest export no longer uses (or only GPI's bills use) show 0 records; kept, with their history.
    for key, m in rows.items():
        if key not in found:
            m.records, m.amount_centavos = 0, 0
    audit(db, user, "imports.matches_loaded", target=f"{len(found)} labels", target_type="import")
    return {"labels": len(found), "new": sum(1 for k in found if k not in rows)}


def fill_in(db, m: ImportMatch, now) -> None:
    """What the export or a recorded answer already says. Same-name accounts are only suggested:
    a name alone can mislead, and the purchase type still has to be chosen."""
    def done(note, **choice):
        for k, v in choice.items():
            setattr(m, k, v)
        m.status, m.note, m.confirmed_by, m.confirmed_at = "confirmed", note, AUTOMATIC, now
    if m.section == "company" and norm(m.source_label) in KNOWN_COMPANIES:
        done(COMPANY_NOTE, company=KNOWN_COMPANIES[norm(m.source_label)])
    elif m.section == "tax" and norm(m.source_label) == "vat" and m.source_code == "12.00":
        done("The export says VAT 12%.", vat_kind="vat")
    elif m.section == "account" and m.account_id is None:
        same = [a for a in posting_accounts(db).values() if norm(a.name) == norm(m.source_label)]
        if len(same) == 1:
            m.account_id, m.note = same[0].id, "Suggested: the same name is in Finance's chart. Check it, choose the purchase type and save."


# --- planning: what each record would become ------------------------------------------------------

def created_records(db, kind: str) -> dict:
    """Zoho ID -> the Finance record it already became."""
    return {r.source_id: r for r in db.scalars(select(ImportRecord).where(
        ImportRecord.source == SOURCE, ImportRecord.kind == kind, ImportRecord.outcome == "created"))}


def supplier_index(db) -> dict:
    out = defaultdict(list)
    for s in db.scalars(select(Supplier)):
        out[norm(s.name)].append(s)
    return out


def posting_accounts(db) -> dict:
    """Accounts a bill line may use: active expense or asset accounts without accounts under them."""
    accounts = list(db.scalars(select(Account)))
    parents = {a.parent_id for a in accounts if a.parent_id}
    return {a.id: a for a in accounts if a.is_active and a.type in ("expense", "asset") and a.id not in parents}


def peso(centavos: int) -> str:
    return f"₱{centavos / 100:,.2f}"


def plan_bills(db, docs: list[dict], settings) -> list[dict]:
    from app.routers.funds import today

    matches = confirmed(db)
    companies_from(matches, docs)
    done = created_records(db, "bill")
    suppliers = supplier_index(db)
    usable = posting_accounts(db)
    s = posting_settings(db)
    withheld_bills = {a["reference"] for d in docs if d["kind"] == "vendor_payment" for a in d["allocations"] if a["withheld"]}
    numbers_here = Counter()
    out = []
    for d in (d for d in docs if d["kind"] == "bill"):
        row = {"sourceId": d["sourceId"], "number": d["number"], "party": d["party"], "date": d["date"], "total": d["total"],
               "company": d["company"], "reasons": [], "outcome": "ready", "bill": None}
        out.append(row)
        if d["sourceId"] in done:
            r = done[d["sourceId"]]
            row.update(outcome="imported", billId=r.bill_id)
            continue
        if d["company"] == "gpi":
            row.update(outcome="skipped", reasons=["Company label confirmed as GPI: not 2MG's bill."])
            continue
        reasons = row["reasons"]
        if d["company"] != "2mg":
            reasons.append(f"Company label “{d['companySource'] or 'none'}” isn't confirmed yet (Settings → Import matching).")
        reasons += [ISSUES[c] for c in d["issues"]]
        if d["sourceId"] in withheld_bills:
            reasons.append(WITHHOLDING_HELD)
        if len(d["sourceId"]) > 60 or len(d["number"]) > 60:
            reasons.append("The Zoho bill ID or number is longer than Finance keeps; it was not shortened.")
        same = suppliers.get(norm(d["party"]), [])
        supplier = same[0] if len(same) == 1 else None
        if not same:
            reasons.append(f"No supplier named “{d['party']}” in Finance.")
        elif len(same) > 1:
            reasons.append(f"{len(same)} suppliers in Finance are named “{d['party']}”; which one isn't clear.")
        elif not supplier.is_active:
            reasons.append(f"Supplier “{supplier.name}” is switched off in Finance.")
        lines = []
        for i, ln in enumerate(d["lines"], 1):
            a, t = matches.get(account_key(ln)), matches.get(tax_key(ln))
            label = ln["account"] or "no account"
            if a is None:
                reasons.append(f"Line {i}: account “{label}” isn't matched and confirmed yet.")
            elif a.account_id not in usable:
                reasons.append(f"Line {i}: “{label}” is matched to an account a bill line can't use (an active expense or asset account with nothing under it).")
            elif a.purchase_type not in PURCHASE_TYPES:
                reasons.append(f"Line {i}: “{label}” has no purchase type confirmed.")
            if t is None or t.vat_kind not in VAT_KINDS:
                reasons.append(f"Line {i}: tax label “{ln['taxName'] or 'blank'}” isn't matched and confirmed yet.")
            if a is not None and t is not None and a.account_id in usable and a.purchase_type in PURCHASE_TYPES and t.vat_kind in VAT_KINDS:
                lines.append({"accountId": a.account_id, "description": (ln["description"] or None) and ln["description"][:200],
                              "amountCentavos": ln["amount"], "vat": t.vat_kind, "withholding": None, "purchaseType": a.purchase_type})
        inclusive = d["original"].get("inclusiveTax")
        if inclusive not in ("true", "false"):
            reasons.append("The export doesn't say whether the amounts include tax.")
        if d["date"] > today(settings).isoformat():
            reasons.append("The bill date is in the future.")
        due = d["dueDate"] or (supplier and (datetime.fromisoformat(d["date"]).date() + timedelta(days=supplier.terms_days)).isoformat())
        if due and due < d["date"]:
            reasons.append("The due date is before the bill date.")
        if supplier is not None:
            key = (supplier.id, d["number"].casefold())
            numbers_here[key] += 1
            if numbers_here[key] > 1:
                reasons.append("Another bill in this file has the same supplier and number.")
            twin = db.scalar(select(Bill).where(Bill.supplier_id == supplier.id, func.lower(Bill.bill_number) == d["number"].lower(), Bill.status != "void"))
            if twin is not None:
                reasons.append(f"This supplier's invoice {d['number']} is already in Finance as bill {twin.no}.")
        if not reasons and len(lines) == len(d["lines"]):
            w = work_out(db, lines, datetime.fromisoformat(d["date"]).date(), inclusive == "true")
            if w.total != d["total"] or w.vat != d["tax"]:
                reasons.append(f"Finance works this bill out as {peso(w.total)} with {peso(w.vat)} VAT; Zoho shows {peso(d['total'])} with {peso(d['tax'])} VAT.")
            if w.vat and not s.input_tax_account_id:
                reasons.append("The Input VAT default account isn't set (Accounting → Default accounts).")
            if not s.payables_account_id and not (supplier.payables_account_id):
                reasons.append("No accounts payable account is set (Default accounts, or the supplier's own).")
            row["bill"] = {"supplier": supplier, "lines": lines, "include": inclusive == "true", "due": due, "worked": w}
        if reasons:
            row["outcome"] = "held"
    return out


def plan_payments(db, docs: list[dict], settings) -> list[dict]:
    from app.routers.funds import today
    from app.routers.payables import set_aside
    from app.routers.vouchers import paying_accounts

    matches = confirmed(db)
    companies_from(matches, docs)
    done = created_records(db, "vendor_payment")
    bills_in = created_records(db, "bill")
    payable_from = {a.id for a in paying_accounts(db)}
    out = []
    for d in (d for d in docs if d["kind"] == "vendor_payment"):
        row = {"sourceId": d["sourceId"], "number": d["number"], "party": d["party"], "date": d["date"], "total": d["total"],
               "company": d["company"], "reasons": [], "outcome": "ready", "voucher": None}
        out.append(row)
        if d["sourceId"] in done:
            row.update(outcome="imported", voucherId=done[d["sourceId"]].voucher_id)
            continue
        if d["company"] == "gpi":
            row.update(outcome="skipped", reasons=["Its bills are GPI's: not 2MG's payment."])
            continue
        reasons = row["reasons"]
        if d["company"] != "2mg" and "mixed_payment" not in d["issues"]:
            reasons.append("Its bills aren't all confirmed as 2MG's (a payment can't mix companies or cover unconfirmed bills).")
        reasons += [PAYMENT_WITHHOLDING_HELD if c == "withholding_evidence" else ISSUES[c] for c in d["issues"]]
        method = d["original"]["method"]
        if method == "check":
            reasons.append("A check payment needs its check number; the export's reference isn't confirmed as the check number.")
        elif method not in ("bank", "cash"):
            reasons.append("Zoho's payment mode isn't one Finance vouchers use (bank transfer, check or cash).")
        if len(d["sourceId"]) > 60:
            reasons.append("The Zoho payment ID is longer than Finance keeps; it was not shortened.")
        if d["date"] > today(settings).isoformat():
            reasons.append("The payment date is in the future.")
        m = matches.get(money_key(d))
        if m is None:
            reasons.append(f"Paid-from account “{d['original']['moneyAccount'] or 'none'}” isn't matched and confirmed yet.")
        elif m.account_id not in payable_from:
            reasons.append("The paid-from account is matched to an account vouchers can't pay from (under CASH).")
        pairs = []
        for a in d["allocations"]:
            r = bills_in.get(a["reference"])
            b = db.get(Bill, r.bill_id) if r is not None and r.bill_id else None
            if b is None:
                reasons.append(f"Bill {a['number'] or a['reference']} isn't in Finance (import its bill first, or it was held).")
                continue
            pairs.append((b, a["cash"]))
        if pairs:
            if len({b.supplier_id for b, _ in pairs}) != 1:
                reasons.append("Its bills belong to different suppliers in Finance.")
            held = set_aside(db, [b.id for b, _ in pairs])
            for b, amount in pairs:
                if b.status != "recorded":
                    reasons.append(f"Bill {b.no} isn't recorded (it may have been voided).")
                elif amount <= 0 or amount > b.payable_centavos - b.paid_centavos - held.get(b.id, 0):
                    reasons.append(f"Bill {b.no} doesn't have {peso(amount)} left to pay.")
                if d["date"] < b.bill_date.isoformat():
                    reasons.append(f"The payment is dated before bill {b.no}.")
        if not reasons:
            row["voucher"] = {"pairs": pairs, "method": method, "paidFrom": m.account_id}
        else:
            row["outcome"] = "held"
    return out


def summary(rows: list[dict]) -> dict:
    counts = Counter(r["outcome"] for r in rows)
    reasons = Counter(reason for r in rows if r["outcome"] == "held" for reason in r["reasons"])
    return {"counts": {k: counts.get(k, 0) for k in ("ready", "held", "skipped", "imported")},
            "reasons": [{"reason": k, "records": n} for k, n in reasons.most_common()],
            "planKey": hashlib.sha256(json.dumps(sorted((r["sourceId"], r["outcome"]) for r in rows)).encode()).hexdigest()}


def rows_out(rows: list[dict]) -> list[dict]:
    keep = ("sourceId", "number", "party", "date", "total", "company", "reasons", "outcome", "billId", "voucherId")
    return [{k: r[k] for k in keep if k in r} for r in rows]


# --- importing ---------------------------------------------------------------------------------

def record(db, run, kind, row, *, bill=None, voucher=None):
    db.add(ImportRecord(run_id=run.id, source=SOURCE, kind=kind, source_id=row["sourceId"], number=row["number"][:60],
                        outcome="created" if (bill or voucher) else row["outcome"], reasons=row["reasons"],
                        bill_id=bill.id if bill else None, voucher_id=voucher.id if voucher else None))


def import_bills(db, settings, user, files: list[dict], plan_key: str) -> dict:
    from app.routers.payables import bill_event, bill_posting

    begin_change(db)
    lock_series(db, "import:zoho")  # one import at a time (PostgreSQL; SQLite's write lock already does it)
    docs = read_pack(files)
    rows = plan_bills(db, docs, settings)
    result = summary(rows)
    if result["planKey"] != plan_key:
        raise HTTPException(409, "Something changed since the preview (a match, a supplier or a bill). Preview again, then import.")
    run = ImportRun(kind="bills", files=[f["name"] for f in files], fingerprint=fingerprint(files), counts=result["counts"],
                    created_by=user.full_name[:120], created_by_id=user.id)
    db.add(run); db.flush()
    who = f"{user.full_name} (Zoho import)"[:120]
    for row in rows:
        if row["outcome"] == "imported":
            continue
        if row["outcome"] != "ready":
            record(db, run, "bill", row)
            continue
        plan, w = row["bill"], row["bill"]["worked"]
        b = Bill(created_by=who, supplier_id=plan["supplier"].id, bill_number=row["number"], bill_date=datetime.fromisoformat(row["date"]).date(),
                 due_date=datetime.fromisoformat(plan["due"]).date(), amounts_include_vat=plan["include"], zoho_ref=row["sourceId"],
                 notes=f"Imported from a Zoho Books export (Zoho bill ID {row['sourceId']}). Approved in Zoho; no approval took place in Finance."[:500],
                 lines=plan["lines"], tax_reviewed=True)
        b.supplier = plan["supplier"]
        db.add(b); db.flush()
        legs, payables = bill_posting(db, b, w)
        e = post(db, b.bill_date, f"Bill from {b.supplier.name}, invoice {b.bill_number} (imported from Zoho)", legs, who,
                 reference=b.bill_number[:80], source="bill", by_id=user.id)
        b.lines = w.lines
        b.net_centavos, b.vat_centavos, b.withheld_centavos, b.total_centavos, b.payable_centavos = w.net, w.vat, w.withheld, w.total, w.payable
        b.status, b.stage, b.entry_id, b.recorded_at, b.recorded_by = "recorded", None, e.id, datetime.now(UTC), who
        b.payables_account_id = payables.id if payables else None
        bill_event(b, "imported", user, "From a Zoho export, with confirmed import matches. Approvals were in Zoho, not replayed here.")
        audit(db, user, "bill.imported", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
        record(db, run, "bill", row, bill=b)
        row["billId"] = b.id
    audit(db, user, "imports.bills", target=f"{result['counts']['ready']} bills", target_type="import", target_id=run.id)
    db.commit()
    return {"runId": run.id, **result, "rows": rows_out(rows)}


def import_payments(db, settings, user, files: list[dict], plan_key: str) -> dict:
    from app.routers.vouchers import METHOD_LABELS, bill_payables, event, next_number

    begin_change(db)
    lock_series(db, "import:zoho")  # one import at a time (PostgreSQL; SQLite's write lock already does it)
    docs = read_pack(files)
    rows = plan_payments(db, docs, settings)
    result = summary(rows)
    if result["planKey"] != plan_key:
        raise HTTPException(409, "Something changed since the preview (a match or a bill). Preview again, then import.")
    run = ImportRun(kind="supplier_payments", files=[f["name"] for f in files], fingerprint=fingerprint(files), counts=result["counts"],
                    created_by=user.full_name[:120], created_by_id=user.id)
    db.add(run); db.flush()
    who = f"{user.full_name} (Zoho import)"[:120]
    for row in rows:
        if row["outcome"] == "imported":
            continue
        if row["outcome"] != "ready":
            record(db, run, "vendor_payment", row)
            continue
        plan = row["voucher"]
        locked(db, Bill, [b.id for b, _ in plan["pairs"]])
        # Read again under the lock: a voucher released meanwhile in Finance may have paid the bill.
        if any(a > b.payable_centavos - b.paid_centavos or b.status != "recorded" for b, a in plan["pairs"]):
            raise HTTPException(409, f"A bill of Zoho payment {row['number']} was paid or changed meanwhile. Preview again, then import.")
        paid_on = datetime.fromisoformat(row["date"]).date()
        supplier = plan["pairs"][0][0].supplier
        doc = next(d for d in docs if d["kind"] == "vendor_payment" and d["sourceId"] == row["sourceId"])
        ref = (doc["original"].get("reference") or "").strip()
        v = PaymentVoucher(number=next_number(db, paid_on), status="released", supplier_id=supplier.id, method=plan["method"],
                           paid_from_id=plan["paidFrom"], total_centavos=sum(a for _, a in plan["pairs"]), zoho_ref=row["sourceId"],
                           notes=(f"Imported from a Zoho Books export: payment {row['number']} (Zoho ID {row['sourceId']})"
                                  + (f", reference “{ref}”" if ref else "") + ". Released in Zoho; no approval took place in Finance.")[:500],
                           prepared_by=who, prepared_by_id=user.id, released_by=who, paid_on=paid_on)
        v.supplier = supplier
        v.lines = [VoucherLine(bill_id=b.id, position=i, amount_centavos=a) for i, (b, a) in enumerate(plan["pairs"])]
        db.add(v); db.flush()
        paid_from = db.get(Account, plan["paidFrom"])
        legs = [Leg(bill_payables(db, b), debit=a, description=f"Bill {b.no} ({b.bill_number})"[:200]) for b, a in plan["pairs"]]
        legs.append(Leg(paid_from, credit=v.total_centavos, description=f"{METHOD_LABELS[v.method]} to {supplier.name}"[:200]))
        e = post(db, paid_on, f"{v.number}: payment to {supplier.name} (imported from Zoho)", legs, who,
                 reference=row["number"][:80] or v.number, source="voucher", by_id=user.id)
        v.entry_id = e.id
        for b, a in plan["pairs"]:
            b.paid_centavos += a
        event(v, "imported", user, "From a Zoho export, with confirmed import matches. Released in Zoho, not replayed here.")
        audit(db, user, "voucher.imported", target=v.number, target_type="voucher", target_id=v.id)
        record(db, run, "vendor_payment", row, voucher=v)
        row["voucherId"] = v.id
    audit(db, user, "imports.supplier_payments", target=f"{result['counts']['ready']} payments", target_type="import", target_id=run.id)
    db.commit()
    return {"runId": run.id, **result, "rows": rows_out(rows)}
