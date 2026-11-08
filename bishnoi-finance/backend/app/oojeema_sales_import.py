"""Q1 sales and customer payments from Oojeema's Sales Journal and Receipt Journal (decided 2026-10-31: "those are
the records used for BIR", Plans/Plan - Q1 imports per area). The same shape as Zoho bills (app/zoho_import.py):
preview, then import exactly what the preview showed; each SI and receipt once; anything unclear held with its
reason, never guessed. Both files come together, and receipts are worked out after the invoices they settle.

One invoice per SI/BI No. The SI/BI No is the official number and is kept exactly, so no BIR series is read, taken
or moved (series_id stays empty). The amounts are the row's own columns: nothing is worked out by Finance's tax
engine, because the journal is already the record filed. A row must add up to be kept. Reference No and Description
are kept as references only: they link to nothing. Customer TIN is as the row has it; blank is allowed (individuals
may have none).

What the file shows, read from the real export (the notes from an earlier probe were only a guide):
- It has no Status column, so a row isn't assumed uncancelled. A cancellation is a positive row and a negative row
  of the same SI, customer and amounts, dated when it was cancelled. That is posted as what it is: the invoice on
  its date, voided with its entry reversed on the cancellation date, so the books carry each on the day Oojeema does.
- A negative row whose original isn't here is held: its invoice would have to be invented.
- Sales to Government and Discount are empty in this file, so how they behave here can't be confirmed: such a row
  is held rather than read by an earlier note's description of them. Non-VAT Sales is held for the same reason:
  2MG's invoices have no such kind.

Accounts are Finance's Default accounts, as for an invoice issued here; the journal names none to match. It tells no
other app and books no cost of goods (the journal has no items).

A receipt (CR/OR No.) has a row per invoice, linked by exact INV No = SI/BI No; each row carries its own amounts, and
Cash + Check + CWT = Accounts Receivable + Overpayment on every real row, which is checked here. Each row becomes
one payment on one invoice, posted as Record payment does, so it reaches Cash receipts and SAWT and comes off the
same way. A receipt is all or nothing: it's one sum of money received, so half of it isn't posted, and that is what
"each record once" counts. A row whose invoice isn't imported (older, or December) holds its receipt until opening
balances exist. Overpayment holds it too: Finance has no account or treatment for it. A negative row exactly undoing
a positive row of the same receipt and invoice is a cancelled receipt: posted, then taken off on the negative row's
date. CWT is posted without an ATC, which the file doesn't have; SAWT then shows no code. The file's account names can
carry bank account numbers, so only a masked label is ever kept or shown (label_of).
"""
import hashlib
import re
from collections import defaultdict
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.audit import audit
from app.import_review import END, MAX_BYTES, START, ReviewError, cents, iso, norm, read_csv
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.locks import begin_change, lock_series, locked
from app.models import Account, ImportLink, ImportMatch, ImportRecord, ImportRun, Invoice, InvoicePayment, InvoiceSeries, JournalEntry
from app.routers.invoices import formatted
from app.routers.tax import LineBody, SaleBody, work_out
from app.tax.packs.ph import invoice as printed
from app.funds import RELEASE_METHODS as METHODS
from app.zoho_import import PackError, closed_on, created_records, fingerprint, links_by_source, record, rows_out, summary

SOURCE = "oojeema"
COLUMNS = ("Transaction Date", "Customer Name", "Customer Tin", "Description", "SI/BI No", "Reference No", "Amount", "Discount", "Output VAT", "Vatable Sales",
           "Sales to Government", "VAT Exempt Sales", "Zero-Rated Sales", "Non-VAT Sales")
MONEY = {"amount": "Amount", "discount": "Discount", "vat": "Output VAT", "vatable": "Vatable Sales", "government": "Sales to Government", "exempt": "VAT Exempt Sales",
         "zero": "Zero-Rated Sales", "nonvat": "Non-VAT Sales"}
# A row's VAT is its own, but it should be 12% of its VATable sales: Oojeema rounds line by line, so a few centavos
# apart is rounding (the file's widest is under 5). Further apart, something else is going on.
VAT_RATE_BP, VAT_ROUNDING = 1200, 5
RECEIPT_COLUMNS = ("Transaction Date", "CR/OR No.", "Customer Name", "Customer Address", "Customer TIN", "RV No", "INV No", "Account Name (DR)", "Cash Amount",
                   "Check Amount", "Other Charges", "CWT", "Overpayment", "Accounts Receivable")
RECEIPT_MONEY = {"cash": "Cash Amount", "check": "Check Amount", "other": "Other Charges", "cwt": "CWT", "over": "Overpayment", "ar": "Accounts Receivable"}
ASK = "Choose two files together: Oojeema's Sales Journal and Receipt Journal exports."
OLDER = "It settles an older invoice; it needs opening balances."
NO_ATC = "ATC not in Oojeema's file"
NOTICE = ("The Sales Journal has no due dates, so an imported invoice is treated as due on its date. Receipts of older invoices wait for opening balances, "
          "and Oojeema's Receipt Journal has no ATC, so its tax withheld posts with the ATC blank.")
ROLE = "deposit_to"
NAMES = dict(printed["summary"]["vat"])
LINES = {"vatable": ("taxable_sales", "VATable sales", "PH_VAT12", "taxable"), "exempt": ("exempt_sales", "VAT-exempt sales", "PH_EXEMPT", "exempt"),
         "zero": ("zero_rated_sales", "Zero-rated sales", "PH_ZERO", "zero_rated")}


def table(content: str, title: str, columns: tuple) -> list[tuple[int, list[str]]] | None:
    """The rows under this report's title and exact headers, if the file is that report."""
    rows = read_csv(content)
    header = next((i for i, r in enumerate(rows[:25]) if [c.strip() for c in r] == list(columns)), None)
    if header is None or not any(norm(c) == title for r in rows[:header] for c in r):
        return None
    if not any(r and norm(r[0]) == "taxpayer trade name" and "2mg" in norm(" ".join(r[1:])) for r in rows[:header]):
        raise PackError("This journal doesn't name 2MG as the taxpayer.")
    out = []
    for n, row in enumerate(rows[header + 1:], header + 2):
        if not any(c.strip() for c in row):
            continue
        if len(row) != len(columns):
            raise PackError(f"Row {n} has a different column count.")
        out.append((n, [c.strip() for c in row]))
    return out


def sale_rows(body) -> list[dict]:
    out = []
    for n, cells in body:
        r = dict(zip(COLUMNS, cells))
        if not r["SI/BI No"]:
            raise PackError(f"Row {n} has no SI/BI No.")
        out.append({"row": n, "number": r["SI/BI No"], "date": iso(r["Transaction Date"]), "party": r["Customer Name"], "tin": r["Customer Tin"] or None,
                    "description": " ".join(r["Description"].split()), "reference": r["Reference No"], **{key: cents(r[column], required=True) for key, column in MONEY.items()}})
    return out


def receipt_rows(body) -> list[dict]:
    out = []
    for n, cells in body:
        r = dict(zip(RECEIPT_COLUMNS, cells))
        if not r["CR/OR No."] or not r["INV No"]:
            raise PackError(f"Row {n} has no CR/OR No. or INV No.")
        out.append({"row": n, "receipt": r["CR/OR No."], "rv": r["RV No"], "invoice": r["INV No"], "date": iso(r["Transaction Date"]), "party": r["Customer Name"],
                    "account": r["Account Name (DR)"], **{key: cents(r[column], required=True) for key, column in RECEIPT_MONEY.items()}})
    return out


def read_pack(files: list[dict]) -> tuple[list[dict], list[dict]]:
    """The two journals, by what each file is, not by its name. Refuses anything else."""
    if len(files) != 2:
        raise PackError(ASK)
    if sum(len(f["content"].encode()) for f in files) > MAX_BYTES:
        raise PackError("Choose no more than 8 MB of CSV contents.")
    sales = receipts = None
    try:
        for f in files:
            if (body := table(f["content"], "sales journal", COLUMNS)) is not None:
                sales = sale_rows(body)
            elif (body := table(f["content"], "receipt journal", RECEIPT_COLUMNS)) is not None:
                receipts = receipt_rows(body)
    except ReviewError as error:
        raise PackError(str(error)) from None
    if sales is None or receipts is None:
        raise PackError(ASK)
    return sales, receipts


def is_pack(files: list[dict]) -> bool:
    """Whether Import matching was given these journals rather than Zoho exports."""
    try:
        return any(table(f["content"], t, c) is not None for f in files for t, c in (("sales journal", COLUMNS), ("receipt journal", RECEIPT_COLUMNS)))
    except (PackError, ReviewError):
        return True  # the journal's own check says what's wrong with it


def label_of(name: str) -> tuple[str, str]:
    """An account as Finance may keep it: no bank account number, only its last four digits, and a hash of the
    whole name, so two accounts that differ only in their numbers stay two rows."""
    masked = re.sub(r"\d[\d\s-]{3,}\d", lambda m: "••••" + re.sub(r"\D", "", m.group())[-4:], name)
    return hashlib.sha256(name.encode()).hexdigest()[:24], masked[:200]


def money_key(name: str) -> tuple:
    return ("money", ROLE, *label_of(name))


def matches_of(db) -> dict:
    return {(m.section, m.role, m.source_code, m.source_label): m for m in db.scalars(select(ImportMatch).where(ImportMatch.source == SOURCE))}


def load_groups(db, files: list[dict], user) -> dict:
    """Saves each deposit account once for Import matching, masked. Nothing else in these journals needs matching."""
    _, receipts = read_pack(files)
    found: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for r in receipts:
        g = found[money_key(r["account"])]
        g[0] += 1
        g[1] += r["cash"] + r["check"]
    rows = matches_of(db)
    now = datetime.now(UTC)
    for key, (count, amount) in found.items():
        m = rows.get(key)
        if m is None:
            m = ImportMatch(source=SOURCE, section=key[0], role=key[1], source_code=key[2], source_label=key[3], status="open")
            db.add(m)
        m.records, m.amount_centavos, m.seen_at = count, amount, now
    for key, m in rows.items():
        if key not in found:
            m.records, m.amount_centavos = 0, 0
    audit(db, user, "imports.matches_loaded", target=f"{len(found)} labels", target_type="import")
    return {"labels": len(found), "new": sum(1 for k in found if k not in rows), "pack": "oojeema"}


def records_for(files: list[dict], m: ImportMatch) -> dict:
    """The receipt rows behind one deposit account, read from the files sent. Saves nothing."""
    _, receipts = read_pack(files)
    key = (m.section, m.role, m.source_code, m.source_label)
    rows = [{"kind": "receipt", "number": r["receipt"], "date": r["date"], "party": r["party"], "amount": r["cash"] + r["check"], "description": f"Settles {r['invoice']}",
             "account": "", "tax": "", "company": ""} for r in receipts if money_key(r["account"]) == key]
    rows.sort(key=lambda r: (r["date"], r["number"]))
    return {"label": m.source_label, "section": m.section, "total": len(rows), "amountCentavos": sum(r["amount"] for r in rows), "rows": rows[:500], "shown": min(len(rows), 500), "perRecord": False}


def problems(r: dict) -> list[str]:
    """What stops one row from being read as it stands."""
    out = []
    if r["discount"]:
        out.append("It has a discount: the file has no example to confirm how a discount sits in its columns.")
    if r["government"]:
        out.append("It's a sale to government: the file has no example to confirm how those sit in its columns.")
    if r["nonvat"]:
        out.append("It has Non-VAT sales, which isn't a kind of sale on 2MG's invoices.")
    if not r["amount"]:
        out.append("Its amount is zero.")
    if r["vatable"] + r["vat"] + r["government"] + r["exempt"] + r["zero"] + r["nonvat"] != r["amount"]:
        out.append("Its columns don't add up to its Amount.")
    if abs(r["vatable"] * VAT_RATE_BP / 10_000 - r["vat"]) > VAT_ROUNDING:
        out.append("Its Output VAT isn't 12% of its VATable sales.")
    if len(r["party"]) > 200 or not r["party"]:
        out.append("Its customer name is missing or longer than Finance keeps.")
    if r["tin"] and len(r["tin"]) > 20:
        out.append("Its TIN is longer than Finance keeps; it was not shortened.")
    if len(r["number"]) > 30 or len(r["reference"]) > 80:
        out.append("Its number or reference is longer than Finance keeps; it was not shortened.")
    return out


def opposite(a: dict, b: dict) -> bool:
    """The negative row b undoes the positive row a exactly: same customer, every amount the opposite."""
    return norm(a["party"]) == norm(b["party"]) and all(a[k] == -b[k] for k in MONEY)


def inside_series(series: list[InvoiceSeries], number: str) -> InvoiceSeries | None:
    """The BIR series a number belongs to: importing it would take a number the series will come to."""
    for s in series:
        rest = number[len(s.prefix):]
        if number.startswith(s.prefix) and rest.isdigit() and s.first_number <= int(rest) <= s.last_number and formatted(s, int(rest)) == number:
            return s
    return None


def plan(db, journal: list[dict], settings) -> list[dict]:
    from app.routers.funds import today

    done = created_records(db, "invoice", SOURCE)
    links = links_by_source(db, "invoice", SOURCE)
    s = posting_settings(db)
    series = list(db.scalars(select(InvoiceSeries)))
    by_si: dict[str, list[dict]] = defaultdict(list)
    for r in journal:
        by_si[r["number"]].append(r)
    taken = {n for (n,) in db.execute(select(Invoice.number).where(Invoice.number.in_(list(by_si))))}
    now = today(settings).isoformat()
    out = []
    for number, group in by_si.items():
        first = next((r for r in group if r["amount"] > 0), group[0])
        row = {"kind": "invoice", "sourceId": number, "number": number, "party": first["party"], "date": first["date"], "total": first["amount"], "company": "2mg",
               "reasons": [], "outcome": "ready", "sale": None, "rows": len(group)}
        out.append(row)
        if number in done:
            link = links.get(number)
            row.update(outcome="imported", invoiceId=link.invoice_id if link else None)
            continue
        inside = [r for r in group if START <= r["date"] <= END]
        if not inside:
            row.update(outcome="skipped", reasons=["Dated outside January 1 to March 31, 2026."])
            continue
        reasons = row["reasons"]
        positive = [r for r in inside if r["amount"] > 0]
        negative = [r for r in inside if r["amount"] < 0]
        reversal = None
        if len(inside) != len(group):
            reasons.append("This SI has rows outside the quarter too; it needs Finance's decision.")
        elif negative and not positive:
            reasons.append("It's a reversal (negative row) with no original in this file; its invoice is older and isn't made up here.")
        elif len(positive) != 1 or len(negative) > 1:
            reasons.append("This SI repeats in a way the file doesn't explain.")
        elif negative:
            reversal = negative[0]
            if not opposite(positive[0], reversal) or reversal["date"] < positive[0]["date"]:
                reasons.append("A negative row has this SI, but it doesn't exactly undo the original.")
        for r in inside:
            reasons += problems(r)
        if number in taken:
            reasons.append("This invoice number is already in Finance.")
        if (within := inside_series(series, number)) is not None:
            reasons.append(f"This number is inside Finance's series “{within.name}”, which would come to it later.")
        for r in inside:
            if r["date"] > now:
                reasons.append("It's dated in the future.")
            if closed := closed_on(s, r["date"]):
                reasons.append(closed)
        if not (s.receivables_account_id and s.sales_account_id and (s.output_tax_account_id or not first["vat"])):
            reasons.append("A default account for invoices isn't set (Accounting → Default accounts).")
        reasons[:] = list(dict.fromkeys(reasons))
        if reasons:
            row["outcome"] = "held"
            continue
        o = positive[0]
        row["sale"] = {"row": o, "reversal": reversal}
        row["choices"] = [o[k] for k in MONEY] + [o["tin"], reversal["date"] if reversal else None]
    return out


def computed_of(db, settings, r: dict) -> tuple[list[dict], dict]:
    """The invoice as it prints, from the row's own columns. The journal has no items: one line per kind of sale.
    work_out supplies only what doesn't depend on the amounts: the seller, as every invoice shows them."""
    shell = work_out(db, settings, SaleBody(on=date.fromisoformat(r["date"]), buyer=None, lines=[LineBody(quantity=1, unit_price_centavos=0)]))
    lines, printed_lines = [], []
    for kind, (_, label, code, bucket) in LINES.items():
        if not r[kind]:
            continue
        tax = r["vat"] if kind == "vatable" else 0
        category = {"vatable": "standard", "exempt": "exempt", "zero": "zero_rated"}[kind]
        lines.append({"ref": None, "description": label, "quantity": 1, "unitPriceCentavos": r[kind] + tax, "discountCentavos": 0, "category": category, "reliefEligible": False})
        printed_lines.append({"ref": None, "description": label, "code": code, "codeName": label, "bucket": bucket, "rateBp": VAT_RATE_BP if kind == "vatable" else 0,
                              "priceCentavos": r[kind] + tax, "baseCentavos": r[kind], "reliefCentavos": 0, "taxableCentavos": r[kind], "taxCentavos": tax, "totalCentavos": r[kind] + tax})
    summary_lines = [{"key": "taxable_sales", "label": NAMES["taxable_sales"], "amountCentavos": r["vatable"]}, {"key": "tax", "label": NAMES["tax"], "amountCentavos": r["vat"]},
                     {"key": "zero_rated_sales", "label": NAMES["zero_rated_sales"], "amountCentavos": r["zero"]}, {"key": "exempt_sales", "label": NAMES["exempt_sales"], "amountCentavos": r["exempt"]}]
    return lines, {**shell, "pricesIncludeTax": True, "buyer": {"name": r["party"], "tin": r["tin"], "address": None, "idNumber": None}, "lines": printed_lines,
                   "summary": summary_lines, "totalDueCentavos": r["amount"]}


def create_invoice(db, settings, user, who: str, ledger, r: dict) -> Invoice:
    """An invoice from one journal row, posted. Its number is the journal's: no series is read, taken or moved."""
    lines, computed = computed_of(db, settings, r)
    notes = f"Imported from Oojeema's Sales Journal. Reference {r['reference'] or 'none'}, description {r['description'] or 'none'}: kept as Oojeema shows them."
    inv = Invoice(status="issued", number=r["number"], customer_name=r["party"], customer_tin=r["tin"], treatment="regular", invoice_date=date.fromisoformat(r["date"]), terms_days=0,
                  reference=r["reference"] or None, notes=notes[:500], prices_include_tax=True, lines=lines, computed=computed, total_centavos=r["amount"], tax_centavos=r["vat"],
                  created_by=who, issued_at=datetime.now(UTC), issued_by=who)
    db.add(inv); db.flush()
    legs = [Leg(db.get(Account, ledger.receivables_account_id), debit=inv.total_centavos), Leg(db.get(Account, ledger.sales_account_id), credit=inv.total_centavos - inv.tax_centavos),
            Leg(db.get(Account, ledger.output_tax_account_id) if ledger.output_tax_account_id else None, credit=inv.tax_centavos)]
    inv.entry_id = post(db, inv.invoice_date, f"{inv.number}: sale to {inv.customer_name} (imported from Oojeema)", legs, who, reference=inv.number, source="invoice", by_id=user.id).id
    audit(db, user, "invoice.imported", target=f"{inv.number} {inv.customer_name}", target_type="invoice", target_id=inv.id)
    return inv


def cancel_invoice(db, user, who: str, inv: Invoice, r: dict) -> None:
    """The journal's reversal row: the invoice voided, its entry reversed on the row's own date."""
    on = date.fromisoformat(r["date"])
    entry = db.get(JournalEntry, inv.entry_id)
    legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
    post(db, on, f"Void of {inv.number}: reversed in Oojeema's Sales Journal", legs, who, reference=inv.number, source="invoice", reverses=entry, by_id=user.id)
    inv.status, inv.void_reason = "void", f"Reversed in Oojeema's Sales Journal on {r['date']}."
    inv.voided_at, inv.voided_by = datetime(on.year, on.month, on.day, tzinfo=UTC), who
    audit(db, user, "invoice.voided", target=f"{inv.number} {inv.customer_name}", target_type="invoice", target_id=inv.id)


def undoes(a: dict, b: dict) -> bool:
    """The negative row b cancels the positive row a of the same receipt and invoice, amount for amount."""
    return a["invoice"] == b["invoice"] and all(a[k] == -b[k] for k in RECEIPT_MONEY) and b["date"] >= a["date"]


def plan_receipts(db, receipts: list[dict], settings, invoices: list[dict]) -> list[dict]:
    """After plan: an invoice ready in this same run counts as here."""
    from app.routers.funds import today
    from app.routers.vouchers import paying_accounts

    done = created_records(db, "receipt", SOURCE)
    links = links_by_source(db, "receipt", SOURCE)
    matches = {k: m for k, m in matches_of(db).items() if m.status == "confirmed"}
    s = posting_settings(db)
    cash_accounts = {a.id for a in paying_accounts(db)}
    here = {r["sourceId"]: r for r in invoices}
    earlier = {i.id: i for i in db.scalars(select(Invoice).where(Invoice.id.in_([r.get("invoiceId") for r in invoices if r.get("invoiceId")])))}
    by_receipt: dict[str, list[dict]] = defaultdict(list)
    for r in receipts:
        by_receipt[r["receipt"]].append(r)
    now = today(settings).isoformat()
    room: dict[str, int] = {}
    out = []
    for number, group in by_receipt.items():
        row = {"kind": "receipt", "sourceId": number, "number": number, "party": group[0]["party"], "date": group[0]["date"], "total": sum(r["cash"] + r["check"] for r in group),
               "company": "2mg", "reasons": [], "outcome": "ready", "receipt": None, "rows": len(group)}
        out.append(row)
        if number in done:
            link = links.get(number)
            row.update(outcome="imported", invoiceId=link.invoice_id if link else None)
            continue
        reasons = row["reasons"]
        positive = [r for r in group if r["ar"] > 0]
        pairs, live = [], list(positive)
        for r in (r for r in group if r["ar"] < 0):
            match = next((p for p in live if undoes(p, r)), None)
            if match is None:
                reasons.append("A negative row doesn't exactly undo a row of this receipt.")
            else:
                live.remove(match)
                pairs.append((match, r))
        for r in group:
            if r["cash"] + r["check"] + r["cwt"] + r["other"] != r["ar"] + r["over"]:
                reasons.append("A row's Cash, Check and CWT don't add up to its Accounts Receivable and Overpayment.")
            if r["other"]:
                reasons.append("It has Other Charges, which Finance's payment has no place for.")
            if r["over"]:
                reasons.append("It has an overpayment, which Finance has no account or treatment for yet.")
            if r["cash"] and r["check"]:
                reasons.append("A row has both cash and a check; Finance's payment has one method.")
            if not r["ar"]:
                reasons.append("A row settles nothing.")
            if not START <= r["date"] <= END:
                reasons.append("It's dated outside January 1 to March 31, 2026.")
            if r["date"] > now:
                reasons.append("It's dated in the future.")
            if closed := closed_on(s, r["date"]):
                reasons.append(closed)
            if len(r["receipt"]) + len(r["rv"]) + 2 > 80:
                reasons.append("Its receipt or RV number is longer than Finance keeps; it was not shortened.")
            m = matches.get(money_key(r["account"]))
            if m is None or m.account_id is None:
                reasons.append(f"Deposit account “{label_of(r['account'])[1]}” isn't matched and confirmed yet.")
            elif m.account_id not in cash_accounts:
                reasons.append("The matched receipt account is non-cash or unavailable for deposits. Its settlement treatment needs review; no cash payment will be imported.")
        for r in live + [p for p, _ in pairs]:
            target = here.get(r["invoice"])
            usable = target is not None and target["outcome"] in ("ready", "imported")
            if not usable:
                reasons.append(OLDER if target is None or target["outcome"] == "skipped" else "Its invoice is held, so this receipt waits for it.")
                continue
            total = target["total"]
            if target["outcome"] == "imported":
                inv = earlier.get(target.get("invoiceId"))
                if inv is None or inv.status != "issued":
                    reasons.append("Its invoice isn't issued in Finance (it may have been voided).")
                    continue
                total = inv.total_centavos - inv.paid_centavos
            elif target["sale"]["reversal"]:
                reasons.append("Its invoice was cancelled in Oojeema.")
                continue
            if r["date"] < target["date"]:
                reasons.append("It's dated before its invoice.")
            room.setdefault(r["invoice"], total)
        reasons[:] = list(dict.fromkeys(reasons))
        if reasons:
            row["outcome"] = "held"
            continue
        row["receipt"] = {"live": live, "pairs": pairs}
        row["choices"] = [[r["invoice"], r["cash"], r["check"], r["cwt"], matches[money_key(r["account"])].account_id] for r in group]
    # Several ready receipts that together exceed an invoice are all held: no winner is picked.
    wanted: dict[str, int] = defaultdict(int)
    for row in out:
        if row["outcome"] == "ready":
            for r in row["receipt"]["live"]:
                wanted[r["invoice"]] += r["ar"]
    over = {k for k, n in wanted.items() if n > room.get(k, 0)}
    for row in out:
        if row["outcome"] == "ready" and any(r["invoice"] in over for r in row["receipt"]["live"]):
            row["reasons"].append("Together these receipts come to more than is owed on an invoice.")
            row.update(outcome="held", receipt=None)
    return out


def planned(db, files: list[dict], settings) -> tuple[list[dict], list[dict]]:
    sales, receipts = read_pack(files)
    invoices = plan(db, sales, settings)
    return invoices, plan_receipts(db, receipts, settings, invoices)


def figures(invoices: list[dict], receipts: list[dict]) -> dict:
    sold = [r["sale"]["row"] for r in invoices if r["outcome"] == "ready"]
    paid = [x for r in receipts if r["outcome"] == "ready" for x in r["receipt"]["live"]]
    return {"amountCentavos": sum(r["amount"] for r in sold), "vatCentavos": sum(r["vat"] for r in sold), "cashCentavos": sum(r["cash"] + r["check"] for r in paid),
            "cwtCentavos": sum(r["cwt"] for r in paid)}


def result_of(invoices: list[dict], receipts: list[dict], files: list[dict]) -> dict:
    return {**summary(invoices + receipts, source_fingerprint=fingerprint(files)), "notice": NOTICE, "figures": figures(invoices, receipts),
            "parts": [{"label": "Invoices", "counts": summary(invoices)["counts"]}, {"label": "Customer receipts", "counts": summary(receipts)["counts"]}]}


def preview(db, settings, files: list[dict]) -> dict:
    invoices, receipts = planned(db, files, settings)
    return {**result_of(invoices, receipts, files), "rows": rows_out(invoices + receipts)}


def create_payment(db, user, who: str, ledger, inv: Invoice, r: dict) -> InvoicePayment:
    """One receipt row on its invoice, posted as Record payment does. The file has no ATC, so none is put in."""
    method, cash = ("cash", r["cash"]) if r["cash"] else ("check", r["check"])
    if r["ar"] > inv.total_centavos - inv.paid_centavos or inv.status != "issued":
        raise HTTPException(409, f"Invoice {inv.number} was paid or changed meanwhile. Preview again, then import.")
    reference = f"{r['receipt']}, {r['rv']}" if r["rv"] else r["receipt"]
    on = date.fromisoformat(r["date"])
    account_id = matches_of(db)[money_key(r["account"])].account_id
    entry = post(db, on, f"{inv.number}: payment from {inv.customer_name}, {METHODS[method]} ({reference}) (imported from Oojeema)", [
        Leg(db.get(Account, account_id), debit=cash),
        *([Leg(db.get(Account, ledger.cwt_account_id) if ledger.cwt_account_id else None, debit=r["cwt"], description=f"Withheld by the customer ({NO_ATC})")] if r["cwt"] else []),
        Leg(db.get(Account, ledger.receivables_account_id), credit=r["ar"]),
    ], who, reference=reference, source="invoice", by_id=user.id)
    pay = InvoicePayment(invoice=inv, paid_on=on, amount_centavos=cash, method=method, reference=reference, recorded_by=who, cwt_centavos=r["cwt"], cwt_atc=None, entry_id=entry.id)
    inv.paid_centavos += r["ar"]
    db.add(pay); db.flush()
    audit(db, user, "invoice.payment_imported", target=f"{inv.number} {inv.customer_name}", target_type="invoice", target_id=inv.id)
    return pay


def take_off(db, user, who: str, inv: Invoice, pay: InvoicePayment, r: dict) -> None:
    """A receipt cancelled in Oojeema: its entry reversed on the negative row's date, the payment kept and marked."""
    on = date.fromisoformat(r["date"])
    entry = db.get(JournalEntry, pay.entry_id)
    legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
    post(db, on, f"{inv.number}: payment taken off (reversed in Oojeema's Receipt Journal)", legs, who, reference=entry.reference, source="invoice", reverses=entry, by_id=user.id)
    pay.removed_at, pay.removed_by = datetime(on.year, on.month, on.day, tzinfo=UTC), who
    inv.paid_centavos -= pay.amount_centavos + pay.cwt_centavos


def import_sales(db, settings, user, files: list[dict], plan_key: str) -> dict:
    begin_change(db)
    lock_series(db, "import:oojeema")  # one import at a time (PostgreSQL; SQLite's write lock already does it)
    invoices, receipts = planned(db, files, settings)
    result = result_of(invoices, receipts, files)
    if result["planKey"] != plan_key:
        raise HTTPException(409, "The files, matches or invoices changed since the preview. Preview again, then import.")
    # Every invoice already here that a receipt touches, locked in one order before the first posting.
    earlier = {r["sourceId"]: r["invoiceId"] for r in invoices if r.get("invoiceId")}
    locked(db, Invoice, [earlier[x["invoice"]] for row in receipts if row["outcome"] == "ready" for x in row["receipt"]["live"] if x["invoice"] in earlier])
    run = ImportRun(kind="oojeema_sales", files=[f["name"] for f in files], fingerprint=fingerprint(files), counts=result["counts"],
                    created_by=user.full_name[:120], created_by_id=user.id)
    db.add(run); db.flush()
    who = f"{user.full_name} (Oojeema import)"[:120]
    ledger = posting_settings(db)
    made: dict[str, Invoice] = {}
    for row in invoices:
        if row["outcome"] == "imported":
            continue
        rec = record(db, run, "invoice", row, created=row["outcome"] == "ready", source=SOURCE)
        if row["outcome"] != "ready":
            continue
        inv = create_invoice(db, settings, user, who, ledger, row["sale"]["row"])
        if row["sale"]["reversal"]:
            cancel_invoice(db, user, who, inv, row["sale"]["reversal"])
        db.flush()
        db.add(ImportLink(record_id=rec.id, invoice_id=inv.id))
        made[row["sourceId"]] = inv
        row["invoiceId"] = inv.id
    held: dict[str, ImportRecord] = {}
    for row in receipts:
        if row["outcome"] != "imported":
            held[row["sourceId"]] = record(db, run, "receipt", row, created=row["outcome"] == "ready", source=SOURCE)
    db.flush()

    def on_invoice(number: str) -> Invoice:
        return made.get(number) or db.get(Invoice, earlier[number])

    # Cancelled receipts first: each is on and off again, so what's left to pay is the same for the rest.
    ready = [row for row in receipts if row["outcome"] == "ready"]
    for row in ready:
        for r, undo in row["receipt"]["pairs"]:
            inv = on_invoice(r["invoice"])
            pay = create_payment(db, user, who, ledger, inv, r)
            take_off(db, user, who, inv, pay, undo)
            db.add(ImportLink(record_id=held[row["sourceId"]].id, invoice_id=inv.id, payment_id=pay.id))
    for row in ready:
        for r in row["receipt"]["live"]:
            inv = on_invoice(r["invoice"])
            pay = create_payment(db, user, who, ledger, inv, r)
            db.add(ImportLink(record_id=held[row["sourceId"]].id, invoice_id=inv.id, payment_id=pay.id))
            row["invoiceId"] = inv.id
    audit(db, user, "imports.oojeema_sales", target=f"{result['parts'][0]['counts']['ready']} invoices, {result['parts'][1]['counts']['ready']} receipts", target_type="import", target_id=run.id)
    db.commit()
    return {"runId": run.id, **result, "rows": rows_out(invoices + receipts)}
