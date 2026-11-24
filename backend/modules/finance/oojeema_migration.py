"""Smart Oojeema COA, Real/Nominal classifier, Dec 31 Opening Balance & Q1 GL tie-out helpers."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.finance.ledger import Leg, post
from modules.finance import payables
from modules.finance.models import (
    Account,
    BankAccount,
    Bill,
    CompanyScopeReview,
    Invoice,
    InvoicePayment,
    JournalEntry,
    JournalLine,
    LedgerSettings,
    PaymentVoucher,
    Supplier,
    TaxProfile,
    VoucherLine,
)
from modules.finance.routers.ledger import type_of

REAL_TYPES = {"asset", "liability", "equity"}
NOMINAL_TYPES = {"income", "expense"}
_CODE_IN_PARENS = re.compile(r"\(([A-Za-z0-9.\-]+)\)?\s*$")


def parse_centavos(raw: str | None) -> int:
    s = (raw or "").strip().replace(",", "")
    if not s or s == "-":
        return 0
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    val = Decimal(s)
    if neg:
        val = -val
    return int((val * 100).quantize(Decimal("1")))


def parse_oojeema_date(raw: str) -> date:
    s = raw.strip()
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized Oojeema date: {raw!r}")


def _csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


def infer_account_type(
    code: str,
    name: str,
    *,
    account_class: str | None = None,
    nature: str | None = None,
    fs_presentation: str | None = None,
) -> str:
    found = type_of(account_class, nature, fs_presentation)
    if found:
        return found
    head = code.split("-", 1)[0]
    if code == "001":
        return "expense"
    if head.isdigit():
        num = int(head)
        if 1 <= num < 2000:
            return "asset"
        if 2000 <= num < 3000:
            return "liability"
        if 3000 <= num < 4000:
            return "equity"
        if 4000 <= num < 5000:
            return "income"
        if 5000 <= num < 7000:
            return "expense"
        if 7000 <= num < 8000:
            return "income"
    low = name.lower()
    if any(k in low for k in ("payable", "deposit", "output")):
        return "liability"
    if "equity" in low or "retained" in low or "summary" in low:
        return "equity"
    if any(k in low for k in ("sales", "revenue", "income")):
        return "income"
    if any(k in low for k in ("expense", "cost", "charge", "discount")):
        return "expense"
    return "asset"


@dataclass(frozen=True)
class CoaSourceRow:
    code: str
    name: str
    account_type: str
    account_class: str | None
    nature: str | None
    parent_name: str | None
    fs_presentation: str | None
    active_in_source: bool
    recovered_from_tb: bool = False


def parse_coa_csv(text: str, *, active_in_source: bool) -> list[CoaSourceRow]:
    rows = _csv_rows(text)
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    idx = {name: i for i, name in enumerate(header)}
    out: list[CoaSourceRow] = []
    for r in rows[1:]:
        if not r or not (r[idx.get("code", 0)] or "").strip():
            continue
        code = r[idx.get("code", 0)].strip()
        name = (r[idx.get("name", 1)] if len(r) > idx.get("name", 1) else "").strip()
        cls = (r[idx["class"]] if "class" in idx and len(r) > idx["class"] else "").strip() or None
        nat = (r[idx["nature"]] if "nature" in idx and len(r) > idx["nature"] else "").strip() or None
        parent = (r[idx["parent"]] if "parent" in idx and len(r) > idx["parent"] else "").strip() or None
        fs = (r[idx["fs presentation"]] if "fs presentation" in idx and len(r) > idx["fs presentation"] else "").strip() or None
        acct_type = infer_account_type(code, name, account_class=cls, nature=nat, fs_presentation=fs)
        out.append(CoaSourceRow(
            code=code,
            name=name[:120],
            account_type=acct_type,
            account_class=cls,
            nature=nat,
            parent_name=parent,
            fs_presentation=fs,
            active_in_source=active_in_source,
            recovered_from_tb=False,
        ))
    return out


@dataclass(frozen=True)
class TrialBalanceRow:
    code: str
    name: str
    prev_cf_centavos: int
    cf_centavos: int
    debit_centavos: int
    credit_centavos: int
    period_centavos: int
    accum_centavos: int


def parse_trial_balance_csv(text: str) -> list[TrialBalanceRow]:
    rows = _csv_rows(text)
    hdr = next(i for i, r in enumerate(rows) if any("total debit" in c.lower() for c in r))
    out: list[TrialBalanceRow] = []
    for r in rows[hdr + 1:]:
        if len(r) < 8:
            continue
        code = r[0].strip()
        if not code or code.lower().startswith("total"):
            continue
        out.append(TrialBalanceRow(
            code=code,
            name=r[1].strip()[:120],
            prev_cf_centavos=parse_centavos(r[2]),
            cf_centavos=parse_centavos(r[3]),
            debit_centavos=parse_centavos(r[4]),
            credit_centavos=parse_centavos(r[5]),
            period_centavos=parse_centavos(r[6]),
            accum_centavos=parse_centavos(r[7]),
        ))
    return out


def merge_and_recover_coa(
    active_rows: list[CoaSourceRow],
    inactive_rows: list[CoaSourceRow],
    *tb_sets: list[TrialBalanceRow],
    gl_blocks: list[GlAccountBlock] | None = None,
) -> tuple[list[CoaSourceRow], list[CoaSourceRow]]:
    by_code: dict[str, CoaSourceRow] = {}
    for row in inactive_rows:
        by_code[row.code] = row
    for row in active_rows:
        by_code[row.code] = row

    recovered: list[CoaSourceRow] = []
    for tb in tb_sets:
        for t in tb:
            if t.code in by_code:
                continue
            inferred = infer_account_type(t.code, t.name)
            rec = CoaSourceRow(
                code=t.code,
                name=t.name,
                account_type=inferred,
                account_class=None,
                nature=None,
                parent_name=None,
                fs_presentation="Balance Sheet" if inferred in REAL_TYPES else "Income Statement",
                active_in_source=True,
                recovered_from_tb=True,
            )
            by_code[t.code] = rec
            recovered.append(rec)
    for blk in gl_blocks or ():
        if blk.code in by_code:
            continue
        clean_name = _CODE_IN_PARENS.sub("", blk.title).strip()[:120] or blk.code
        inferred = infer_account_type(blk.code, clean_name)
        rec = CoaSourceRow(
            code=blk.code,
            name=clean_name,
            account_type=inferred,
            account_class=None,
            nature=None,
            parent_name=None,
            fs_presentation="Balance Sheet" if inferred in REAL_TYPES else "Income Statement",
            active_in_source=True,
            recovered_from_tb=True,
        )
        by_code[blk.code] = rec
        recovered.append(rec)
    return list(by_code.values()), recovered


def classify_real_vs_nominal_exceptions(rows: list[CoaSourceRow]) -> list[dict]:
    """Compare Finance Head Malou's 001-4000 (Real) vs >4000 (Nominal) rule against actual FS presentation/type."""
    exceptions: list[dict] = []
    for row in sorted(rows, key=lambda x: x.code):
        head = row.code.split("-", 1)[0]
        if not head.isdigit():
            continue
        num = int(head)
        real_by_code = 1 <= num <= 4000
        real_by_type = row.account_type in REAL_TYPES
        if real_by_code != real_by_type:
            exceptions.append({
                "code": row.code,
                "name": row.name,
                "type": row.account_type,
                "fsPresentation": row.fs_presentation,
                "activeInSource": row.active_in_source,
                "reason": "Code is 001-4000 but account is Nominal (Income Statement)" if real_by_code else "Code is >4000 but account is Real (Balance Sheet)",
            })
    return exceptions


@dataclass
class GlAccountBlock:
    code: str
    title: str
    beginning_centavos: int
    lines: list[tuple[date, str, str, int, int]]


def parse_gl_csv(text: str) -> list[GlAccountBlock]:
    rows = _csv_rows(text)
    hdr = next(i for i, r in enumerate(rows) if r and r[0].strip().lower() == "transaction date")
    blocks: list[GlAccountBlock] = []
    current: GlAccountBlock | None = None
    for r in rows[hdr + 1:]:
        if not any(c.strip() for c in r):
            continue
        first = r[0].strip()
        if len(r) == 1 or all(not c.strip() for c in r[1:]):
            m = _CODE_IN_PARENS.search(first)
            if m:
                current = GlAccountBlock(code=m.group(1), title=first, beginning_centavos=0, lines=[])
                blocks.append(current)
            continue
        if current is None:
            continue
        if first.lower() == "beginning balance":
            current.beginning_centavos = parse_centavos(r[7]) - parse_centavos(r[8])
            continue
        if not first or first.lower() in ("subtotal", "balance", "totals:") or (len(r) > 6 and r[6].strip().lower() in ("subtotal", "balance")):
            continue
        if len(r) >= 9:
            dr = parse_centavos(r[7])
            cr = parse_centavos(r[8])
            if dr == 0 and cr == 0:
                continue
            dt = parse_oojeema_date(first)
            voucher = r[6].strip() or r[5].strip() or f"LINE-{len(current.lines)+1}"
            memo = " | ".join(p for p in (r[1].strip(), r[2].strip()) if p)[:280]
            current.lines.append((dt, voucher, memo, dr, cr))
    return blocks


def import_oojeema_coa_and_opening(
    db: Session,
    *,
    active_coa_csv: str,
    inactive_coa_csv: str,
    dec_tb_csv: str,
    q1_tb_csv: str | None = None,
    gl_csv: str | None = None,
    opening_date: date = date(2025, 12, 31),
    reviewed_by: str = "Migration",
    deactivate_inactive: bool = True,
) -> dict:
    active_rows = parse_coa_csv(active_coa_csv, active_in_source=True)
    inactive_rows = parse_coa_csv(inactive_coa_csv, active_in_source=False)
    dec_tb = parse_trial_balance_csv(dec_tb_csv)
    q1_tb = parse_trial_balance_csv(q1_tb_csv) if q1_tb_csv else []
    gl_blocks = parse_gl_csv(gl_csv) if gl_csv else []

    merged, recovered = merge_and_recover_coa(active_rows, inactive_rows, dec_tb, q1_tb, gl_blocks=gl_blocks)
    existing = {a.code: a for a in db.scalars(select(Account))}

    added = 0
    now = datetime.now(UTC)
    for row in merged:
        if row.code in existing:
            acc = existing[row.code]
            if not acc.is_active:
                acc.is_active = True
        else:
            acc = Account(
                code=row.code,
                name=row.name,
                type=row.account_type,
                description="Recovered from Oojeema Trial Balance" if row.recovered_from_tb else None,
                is_active=True,
            )
            db.add(acc)
            db.flush()
            existing[row.code] = acc
            added += 1
        if db.get(CompanyScopeReview, ("account", acc.id)) is None:
            db.add(CompanyScopeReview(
                subject_kind="account",
                subject_id=acc.id,
                scope="2mg",
                evidence={"source": "oojeema migration", "recoveredFromTb": row.recovered_from_tb},
                reviewed_by=reviewed_by,
                reviewed_at=now,
            ))

    by_name = {a.name.strip().lower(): a for a in existing.values()}
    for row in merged:
        if row.parent_name and existing[row.code].parent_id is None:
            p = by_name.get(row.parent_name.strip().lower())
            if p is not None and p.id != existing[row.code].id:
                existing[row.code].parent_id = p.id

    # Build Dec 31, 2025 balanced Opening Entry (Real accounts carry Dec 31 Accumulated Balance;
    # Nominal 2025 P&L nets into 3103-000 Income Summary / Retained Earnings so 2026 starts at 0).
    income_summary = existing.get("3103-000")
    if income_summary is None:
        s_row = db.get(LedgerSettings, 1)
        income_summary = db.get(Account, s_row.retained_earnings_account_id) if s_row and s_row.retained_earnings_account_id else None
    if income_summary is None:
        raise ValueError("Missing equity account (3103-000 Income Summary or retained earnings) to close Dec 2025 net income.")

    legs: list[Leg] = []
    nominal_net_centavos = 0
    for row in dec_tb:
        if row.accum_centavos == 0:
            continue
        acc = existing[row.code]
        if acc.type in REAL_TYPES:
            if row.accum_centavos > 0:
                legs.append(Leg(acc, debit=row.accum_centavos, description="Dec 31, 2025 opening balance"))
            else:
                legs.append(Leg(acc, credit=-row.accum_centavos, description="Dec 31, 2025 opening balance"))
        else:
            nominal_net_centavos += row.accum_centavos

    if nominal_net_centavos > 0:
        legs.append(Leg(income_summary, debit=nominal_net_centavos, description="2025 Net P&L closed to Income Summary"))
    elif nominal_net_centavos < 0:
        legs.append(Leg(income_summary, credit=-nominal_net_centavos, description="2025 Net P&L closed to Income Summary"))

    opening_entry = post(
        db,
        opening_date,
        f"Opening balances as of {opening_date:%d %b %Y} (Oojeema Dec 2025 TB)",
        legs,
        reviewed_by,
        source="opening",
    )

    deactivated = 0
    if deactivate_inactive:
        s_row = db.get(LedgerSettings, 1)
        protected_ids = (
            {
                getattr(s_row, c.name)
                for c in LedgerSettings.__table__.columns
                if c.name.endswith("_account_id") and getattr(s_row, c.name)
            }
            if s_row is not None
            else set()
        )
        for row in inactive_rows:
            acc = existing.get(row.code)
            if acc is not None and acc.id not in protected_ids and acc.is_active:
                acc.is_active = False
                deactivated += 1

    db.flush()
    return {
        "accountsTotal": len(merged),
        "accountsAdded": added,
        "recoveredFromTb": len(recovered),
        "recoveredCodes": [r.code for r in recovered],
        "openingEntryId": opening_entry.id,
        "openingEntryNumber": opening_entry.number,
        "openingLines": len(legs),
        "nominalNetClosedCentavos": nominal_net_centavos,
        "deactivated": deactivated,
        "realNominalExceptions": classify_real_vs_nominal_exceptions(merged),
    }


def post_gl_q1_movements(
    db: Session,
    gl_csv: str,
    *,
    posted_by: str = "Migration",
    source: str = "oojeema_gl",
) -> dict:
    """Post balanced Q1 General Ledger vouchers (after reactivating any historical codes needed for posting)."""
    blocks = parse_gl_csv(gl_csv)
    by_code = {a.code: a for a in db.scalars(select(Account))}

    # Group lines by (voucher_no, entry_date)
    grouped: dict[tuple[str, date], list[tuple[Account, int, int, str]]] = {}
    missing_codes: set[str] = set()
    for blk in blocks:
        acc = by_code.get(blk.code)
        if acc is None:
            missing_codes.add(blk.code)
            continue
        for dt, voucher, memo, dr, cr in blk.lines:
            grouped.setdefault((voucher, dt), []).append((acc, dr, cr, memo))

    if missing_codes:
        raise ValueError(f"GL references accounts not in Finance COA: {sorted(missing_codes)[:10]}")

    temporarily_reactivated: list[Account] = []
    for acc in by_code.values():
        if not acc.is_active:
            acc.is_active = True
            temporarily_reactivated.append(acc)

    posted_entries = 0
    unbalanced: list[dict] = []
    for (voucher, dt), lines in sorted(grouped.items(), key=lambda x: (x[0][1], x[0][0])):
        dr_sum = sum(x[1] for x in lines)
        cr_sum = sum(x[2] for x in lines)
        if dr_sum != cr_sum:
            unbalanced.append({"voucher": voucher, "date": dt.isoformat(), "debit": dr_sum, "credit": cr_sum})
            continue
        legs = [Leg(acc, debit=dr, credit=cr, description=memo or None) for acc, dr, cr, memo in lines]
        post(db, dt, f"Oojeema Q1 {voucher}", legs, posted_by, reference=voucher, source=source)
        posted_entries += 1

    for acc in temporarily_reactivated:
        acc.is_active = False

    db.flush()
    return {
        "blocksParsed": len(blocks),
        "vouchersPosted": posted_entries,
        "unbalancedVouchers": unbalanced,
    }


def _clean_tin_parts(raw: str | None) -> tuple[str | None, str]:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) < 9:
        return None, "00000"
    tin = f"{digits[:3]}-{digits[3:6]}-{digits[6:9]}"
    branch = digits[9:14].ljust(5, "0") if len(digits) > 9 else "00000"
    return tin, branch


def _pick_withholding_code(base_centavos: int, tax_centavos: int) -> str | None:
    if tax_centavos <= 0 or base_centavos <= 0:
        return None
    bp = round(tax_centavos * 10_000 / base_centavos)
    if bp <= 150:
        return "WC158"
    if bp <= 350:
        return "WC160"
    if bp <= 750:
        return "WC100"
    if bp <= 1250:
        return "WC010"
    return "WC011"


def _pick_customer_cwt_atc(cwt_centavos: int, settled_centavos: int, inv_total_centavos: int) -> str | None:
    if cwt_centavos <= 0:
        return None
    if settled_centavos > 0:
        bp_settled = round(cwt_centavos * 10_000 / settled_centavos)
        if 400 <= bp_settled <= 1100:
            return "WV010"
    if inv_total_centavos > 0:
        bp_inv = round(cwt_centavos * 10_000 / inv_total_centavos)
        bp_inv_net = round(cwt_centavos * 10_000 / (inv_total_centavos / 1.12))
        if bp_inv == 200 or bp_inv_net == 200:
            return "WC160"
    return "WC158"


def import_oojeema_operational_records(
    db: Session,
    *,
    vendors_csv: str,
    ar_aging_csv: str,
    ap_aging_csv: str,
    sales_journal_csv: str,
    receipt_journal_csv: str,
    purchase_journal_csv: str,
    disbursement_journal_csv: str,
    expense_register_csv: str,
    imported_by: str = "Migration",
) -> dict:
    """Populate TaxProfile, LedgerSettings, Suppliers, Invoices, Payments, Bills, and PaymentVouchers
    from Oojeema operational exports without duplicating GL journal entries."""
    now = datetime.now(UTC)
    by_code = {a.code: a for a in db.scalars(select(Account))}

    tp = db.get(TaxProfile, 1)
    if tp is None:
        tp = TaxProfile(id=1)
        db.add(tp)
    tp.registered_name = "2MG INCORPORATED"
    tp.trade_name = "2MG INCORPORATED"
    tp.tin = "010-065-182"
    tp.branch_code = "00000"
    tp.rdo_code = "53B"
    tp.registered_address = "17 VATICAN BLDG. VATICAN CITY DRIVE BF RESORT VILLAGE TALON DOS LAS PINAS CITY"
    tp.regime = "vat"
    tp.fiscal_month_end = 12

    ls = db.get(LedgerSettings, 1)
    if ls is None:
        ls = LedgerSettings(id=1)
        db.add(ls)

    def _acc_id(*codes: str) -> str | None:
        for c in codes:
            if c in by_code:
                return by_code[c].id
        return None

    ls.cash_account_id = _acc_id("1110-000", "0001-000")
    ls.bank_account_id = _acc_id("1215-2MG", "1217-2MG", "0001-003")
    ls.check_account_id = _acc_id("1215-2MG", "1217-2MG", "0001-003")
    ls.ewallet_account_id = _acc_id("1110-000", "0001-000")
    ls.receivables_account_id = _acc_id("1301-000")
    ls.sales_account_id = _acc_id("4100-000", "4000-000")
    ls.output_tax_account_id = _acc_id("2315-000")
    ls.payables_account_id = _acc_id("2101-000")
    ls.input_tax_account_id = _acc_id("1600-000")
    ls.withholding_account_id = _acc_id("2306-000", "2307-000")
    ls.cwt_account_id = _acc_id("1507-000")
    ls.cogs_account_id = _acc_id("5000-000", "5301-000")
    ls.inventory_account_id = _acc_id("1700-000")
    ls.capital_account_id = _acc_id("3100-000")
    ls.retained_earnings_account_id = _acc_id("3103-000")
    ls.drawings_account_id = _acc_id("3100-000")
    expense_default_id = _acc_id("6000-000", "5000-000", "6408-000") or next(a.id for a in by_code.values() if a.type == "expense")

    gl_entries = {e.reference: e.id for e in db.scalars(select(JournalEntry).where(JournalEntry.reference.is_not(None)))}

    suppliers_by_name: dict[str, Supplier] = {s.name.strip().lower(): s for s in db.scalars(select(Supplier))}
    v_rows = _csv_rows(vendors_csv)
    suppliers_added = 0
    for r in v_rows[1:]:
        if len(r) < 2 or not r[1].strip():
            continue
        name = r[1].strip()[:200]
        key = name.lower()
        tin, branch = _clean_tin_parts(r[5] if len(r) > 5 else None)
        addr_parts = [r[i].strip() for i in (6, 7, 8, 9) if len(r) > i and r[i].strip()]
        addr = ", ".join(addr_parts)[:300] or None
        if key in suppliers_by_name:
            sup = suppliers_by_name[key]
            if tin and not sup.tin:
                sup.tin, sup.branch_code = tin, branch
            if addr and not sup.address:
                sup.address = addr
            continue
        sup = Supplier(
            name=name,
            company_name=name,
            tin=tin,
            branch_code=branch,
            address=addr,
            email=(r[2].strip()[:254] or None) if len(r) > 2 else None,
            mobile=(r[3].strip()[:40] or None) if len(r) > 3 else None,
            phone=(r[4].strip()[:40] or None) if len(r) > 4 else None,
            origin=payables.origin_by_name(name),
            vat_registered=True,
            tax_defaults_confirmed=True,
            payables_account_id=ls.payables_account_id,
            is_active=True,
            created_by=imported_by,
        )
        db.add(sup)
        db.flush()
        db.merge(CompanyScopeReview(subject_kind="supplier", subject_id=sup.id, scope="2mg", evidence={"source": "oojeema vendor export"}, reviewed_by=imported_by, reviewed_at=now))
        suppliers_by_name[key] = sup
        suppliers_added += 1

    def _get_supplier(raw_name: str, raw_tin: str | None = None, raw_addr: str | None = None) -> Supplier:
        nonlocal suppliers_added
        clean = (raw_name or "").strip()[:200] or "Unnamed Supplier"
        key = clean.lower()
        tin, branch = _clean_tin_parts(raw_tin)
        addr = (raw_addr or "").strip()[:300] or None
        if key in suppliers_by_name:
            s = suppliers_by_name[key]
            if tin and not s.tin:
                s.tin, s.branch_code = tin, branch
            if addr and not s.address:
                s.address = addr
            return s
        s = Supplier(
            name=clean,
            company_name=clean,
            tin=tin,
            branch_code=branch,
            address=addr,
            origin=payables.origin_by_name(clean),
            vat_registered=True,
            tax_defaults_confirmed=True,
            payables_account_id=ls.payables_account_id,
            is_active=True,
            created_by=imported_by,
        )
        db.add(s)
        db.flush()
        db.merge(CompanyScopeReview(subject_kind="supplier", subject_id=s.id, scope="2mg", evidence={"source": "oojeema journal"}, reviewed_by=imported_by, reviewed_at=now))
        suppliers_by_name[key] = s
        suppliers_added += 1
        return s

    invoices_by_no: dict[str, Invoice] = {i.number: i for i in db.scalars(select(Invoice))}
    ar_rows = _csv_rows(ar_aging_csv)
    ar_hdr = next(i for i, r in enumerate(ar_rows) if r and r[0].strip() == "Customer")
    ar_added = 0
    for r in ar_rows[ar_hdr + 1:]:
        if len(r) < 9:
            continue
        cust, ref = r[0].strip(), r[1].strip()
        if not cust or not ref or cust.lower().startswith("total"):
            continue
        bal = parse_centavos(r[8])
        if bal <= 0 or ref in invoices_by_no:
            continue
        inv_dt = parse_oojeema_date(r[2])
        due_dt = parse_oojeema_date(r[3]) if r[3].strip() else inv_dt
        terms = max(0, (due_dt - inv_dt).days)
        summary = [
            {"key": "taxable_sales", "label": "VATable sales", "amountCentavos": 0},
            {"key": "tax", "label": "Output VAT (12%)", "amountCentavos": 0},
            {"key": "zero_rated_sales", "label": "Zero-rated sales", "amountCentavos": 0},
            {"key": "exempt_sales", "label": "VAT-exempt sales", "amountCentavos": bal},
            {"key": "non_taxable_sales", "label": "Non-VAT sales", "amountCentavos": 0},
        ]
        inv = Invoice(
            status="issued",
            number=ref[:30],
            customer_name=cust[:200],
            treatment="regular",
            invoice_date=inv_dt,
            terms_days=terms,
            reference="Dec 31, 2025 Opening AR",
            prices_include_tax=True,
            lines=[{"ref": None, "description": "Opening AR Balance", "quantity": 1, "unitPriceCentavos": bal, "discountCentavos": 0, "category": "exempt", "reliefEligible": False}],
            computed={"pricesIncludeTax": True, "buyer": {"name": cust[:200], "tin": None, "address": None, "idNumber": None}, "lines": [], "summary": summary, "totalDueCentavos": bal},
            total_centavos=bal,
            tax_centavos=0,
            paid_centavos=0,
            created_by=imported_by,
            issued_at=now,
            issued_by=imported_by,
        )
        db.add(inv)
        invoices_by_no[inv.number] = inv
        ar_added += 1

    sj_rows = _csv_rows(sales_journal_csv)
    sj_hdr = next(i for i, r in enumerate(sj_rows) if r and r[0].strip() == "Transaction Date")
    sj_grouped: dict[str, list[list[str]]] = {}
    for r in sj_rows[sj_hdr + 1:]:
        if len(r) < 14:
            continue
        dt_s, si_no = r[0].strip(), r[4].strip()
        if not dt_s or not si_no or dt_s.lower().startswith("total"):
            continue
        sj_grouped.setdefault(si_no, []).append(r)

    q1_invoices_added = 0
    for si_no, grp in sj_grouped.items():
        if si_no in invoices_by_no:
            continue
        pos = [r for r in grp if parse_centavos(r[6]) > 0]
        neg = [r for r in grp if parse_centavos(r[6]) < 0]
        r0 = pos[0] if pos else grp[0]
        is_void = (not pos) or (len(neg) > 0 and sum(parse_centavos(x[6]) for x in grp) <= 0)
        inv_dt = parse_oojeema_date(r0[0])
        cust = r0[1].strip()[:200] or "Customer"
        tin, _ = _clean_tin_parts(r0[2])
        amt = abs(parse_centavos(r0[6]))
        vat = abs(parse_centavos(r0[8]))
        vatable = abs(parse_centavos(r0[9])) + abs(parse_centavos(r0[10]))
        exempt = abs(parse_centavos(r0[11]))
        zero = abs(parse_centavos(r0[12]))
        non_vat = abs(parse_centavos(r0[13]))
        summary = [
            {"key": "taxable_sales", "label": "VATable sales", "amountCentavos": vatable},
            {"key": "tax", "label": "Output VAT (12%)", "amountCentavos": vat},
            {"key": "zero_rated_sales", "label": "Zero-rated sales", "amountCentavos": zero},
            {"key": "exempt_sales", "label": "VAT-exempt sales", "amountCentavos": exempt},
            {"key": "non_taxable_sales", "label": "Non-VAT sales", "amountCentavos": non_vat},
        ]
        inv = Invoice(
            status="void" if is_void else "issued",
            number=si_no[:30],
            customer_name=cust,
            customer_tin=tin,
            treatment="regular",
            invoice_date=inv_dt,
            terms_days=30,
            reference=(r0[3].strip() or r0[5].strip() or None),
            prices_include_tax=True,
            lines=[{"ref": r0[5].strip() or None, "description": r0[3].strip() or "Sales", "quantity": 1, "unitPriceCentavos": amt, "discountCentavos": abs(parse_centavos(r0[7])), "category": "standard" if vat else "exempt", "reliefEligible": False}],
            computed={"pricesIncludeTax": True, "buyer": {"name": cust, "tin": tin, "address": None, "idNumber": None}, "lines": [], "summary": summary, "totalDueCentavos": amt},
            total_centavos=amt,
            tax_centavos=vat,
            paid_centavos=0,
            entry_id=gl_entries.get(si_no),
            created_by=imported_by,
            issued_at=now,
            issued_by=imported_by,
            voided_at=now if is_void else None,
            voided_by=imported_by if is_void else None,
            void_reason="Cancelled in Oojeema Sales Journal" if is_void else None,
        )
        db.add(inv)
        invoices_by_no[inv.number] = inv
        q1_invoices_added += 1
    db.flush()

    rj_rows = _csv_rows(receipt_journal_csv)
    rj_hdr = next(i for i, r in enumerate(rj_rows) if r and r[0].strip() == "Transaction Date")
    rj_live: list[list[str]] = []
    for r in rj_rows[rj_hdr + 1:]:
        if len(r) < 14:
            continue
        if not r[0].strip() or r[0].strip().lower().startswith("total"):
            continue
        ar_amt = parse_centavos(r[13])
        if ar_amt < 0:
            for idx, prev in enumerate(rj_live):
                if prev[1].strip() == r[1].strip() and prev[6].strip() == r[6].strip() and parse_centavos(prev[13]) == -ar_amt:
                    rj_live.pop(idx)
                    break
            continue
        if ar_amt > 0 or parse_centavos(r[8]) > 0 or parse_centavos(r[9]) > 0:
            rj_live.append(r)

    payments_added = 0
    for r in rj_live:
        dt = parse_oojeema_date(r[0])
        or_no, cust, addr, raw_tin, rv_no, inv_no = r[1].strip(), r[2].strip(), r[3].strip(), r[4].strip(), r[5].strip(), r[6].strip()
        cash_c, check_c, cwt_c, ar_c = parse_centavos(r[8]), parse_centavos(r[9]), parse_centavos(r[11]), parse_centavos(r[13])
        received = cash_c + check_c
        if received <= 0 and cwt_c <= 0:
            continue
        tin, _ = _clean_tin_parts(raw_tin)
        inv = invoices_by_no.get(inv_no)
        if inv is None:
            amt = max(ar_c, received + cwt_c)
            inv = Invoice(
                status="issued",
                number=(inv_no or f"PRIOR-{or_no}")[:30],
                customer_name=cust[:200] or "Customer",
                customer_tin=tin,
                customer_address=addr[:300] or None,
                treatment="regular",
                invoice_date=date(2025, 12, 15),
                terms_days=30,
                reference="Prior Period Invoice",
                prices_include_tax=True,
                lines=[{"ref": None, "description": "Prior Period Invoice", "quantity": 1, "unitPriceCentavos": amt, "discountCentavos": 0, "category": "exempt", "reliefEligible": False}],
                computed={"pricesIncludeTax": True, "buyer": {"name": cust[:200], "tin": tin, "address": addr[:300] or None, "idNumber": None}, "lines": [], "summary": [{"key": "exempt_sales", "label": "VAT-exempt sales", "amountCentavos": amt}], "totalDueCentavos": amt},
                total_centavos=amt,
                tax_centavos=0,
                paid_centavos=0,
                created_by=imported_by,
                issued_at=now,
                issued_by=imported_by,
            )
            db.add(inv)
            db.flush()
            invoices_by_no[inv.number] = inv
        else:
            if tin and not inv.customer_tin:
                inv.customer_tin = tin
            if addr and not inv.customer_address:
                inv.customer_address = addr[:300]

        cwt_val = max(0, cwt_c)
        cwt_atc = _pick_customer_cwt_atc(cwt_val, received + cwt_val, inv.total_centavos)
        pay = InvoicePayment(
            invoice_id=inv.id,
            paid_on=dt,
            amount_centavos=received,
            method="check" if check_c > 0 else "bank",
            reference=f"{or_no} ({rv_no})"[:80] if rv_no else or_no[:80],
            cwt_centavos=cwt_val,
            cwt_atc=cwt_atc,
            cwt_certificate=or_no[:60] if cwt_val > 0 else None,
            entry_id=gl_entries.get(rv_no) or gl_entries.get(or_no),
            recorded_by=imported_by,
        )
        db.add(pay)
        inv.paid_centavos = min(inv.total_centavos, inv.paid_centavos + received + cwt_val)
        payments_added += 1
    db.flush()

    bills_by_ref: dict[str, Bill] = {b.oojeema_ref: b for b in db.scalars(select(Bill)) if b.oojeema_ref}
    ap_rows = _csv_rows(ap_aging_csv)
    ap_hdr = next(i for i, r in enumerate(ap_rows) if r and r[0].strip() == "Vendor Name")
    ap_added = 0
    for r in ap_rows[ap_hdr + 1:]:
        if len(r) < 9:
            continue
        vname, ref = r[0].strip(), r[1].strip()
        if not vname or not ref or vname.lower().startswith("total"):
            continue
        bal = parse_centavos(r[8])
        if bal <= 0 or ref in bills_by_ref:
            continue
        b_dt = parse_oojeema_date(r[2])
        d_dt = parse_oojeema_date(r[3]) if r[3].strip() else b_dt
        sup = _get_supplier(vname)
        b = Bill(
            status="recorded",
            supplier_id=sup.id,
            bill_number=ref[:60],
            bill_date=b_dt,
            due_date=d_dt,
            oojeema_ref=ref[:60],
            amounts_include_vat=False,
            lines=[{"accountId": expense_default_id, "description": "Dec 31, 2025 Opening AP", "amountCentavos": bal, "vat": "none", "withholding": None, "noWithholding": "not_covered", "purchaseType": "other_goods"}],
            tax_reviewed=True,
            net_centavos=bal,
            vat_centavos=0,
            withheld_centavos=0,
            total_centavos=bal,
            payable_centavos=bal,
            paid_centavos=0,
            payables_account_id=ls.payables_account_id,
            created_by=imported_by,
            recorded_at=now,
            recorded_by=imported_by,
            approved_by=imported_by,
            approved_at=now,
        )
        db.add(b)
        bills_by_ref[ref] = b
        ap_added += 1

    pj_rows = _csv_rows(purchase_journal_csv)
    pj_hdr = next(i for i, r in enumerate(pj_rows) if r and r[0].strip() == "Transaction Date")
    pj_grouped: dict[str, list[list[str]]] = {}
    for r in pj_rows[pj_hdr + 1:]:
        if len(r) < 14:
            continue
        if not r[0].strip() or r[0].strip().lower().startswith("total"):
            continue
        doc_no = r[7].strip() or r[6].strip()
        if not doc_no:
            continue
        pj_grouped.setdefault(doc_no, []).append(r)

    q1_bills_added = 0
    supplier_atc_counts: dict[str, dict[str, int]] = {}
    for doc_no, grp in pj_grouped.items():
        if doc_no in bills_by_ref:
            continue
        pos = [r for r in grp if parse_centavos(r[13]) > 0]
        r0 = pos[0] if pos else grp[0]
        is_void = r0[5].strip().upper() == "CANCELLED" or not pos or sum(parse_centavos(x[13]) for x in grp) <= 0
        b_dt = parse_oojeema_date(r0[0])
        sup = _get_supplier(r0[1], r0[3], r0[2])
        non_vat = abs(parse_centavos(r0[8]))
        vat_goods = abs(parse_centavos(r0[9]))
        vat_svcs = abs(parse_centavos(r0[10]))
        in_vat = abs(parse_centavos(r0[11]))
        ewt = abs(parse_centavos(r0[12]))
        total_base = non_vat + vat_goods + vat_svcs
        atc = _pick_withholding_code(vat_goods + vat_svcs or total_base, ewt)
        if atc and not is_void:
            counts = supplier_atc_counts.setdefault(sup.id, {})
            counts[atc] = counts.get(atc, 0) + 1
        no_wh_reason = "foreign" if sup.origin == "foreign" else ("not_covered" if not atc else None)

        b_lines: list[dict] = []
        if vat_goods > 0:
            b_lines.append({"accountId": ls.inventory_account_id or expense_default_id, "description": r0[4].strip() or "Goods purchase", "amountCentavos": vat_goods, "vat": "vat", "withholding": atc if vat_goods >= vat_svcs else None, "noWithholding": None if (atc and vat_goods >= vat_svcs) else no_wh_reason, "purchaseType": "other_goods"})
        if vat_svcs > 0:
            b_lines.append({"accountId": expense_default_id, "description": r0[4].strip() or "Services purchase", "amountCentavos": vat_svcs, "vat": "vat", "withholding": atc if vat_svcs > vat_goods else None, "noWithholding": None if (atc and vat_svcs > vat_goods) else no_wh_reason, "purchaseType": "services"})
        if non_vat > 0 or not b_lines:
            b_lines.append({"accountId": expense_default_id, "description": r0[4].strip() or "Non-VAT purchase", "amountCentavos": non_vat or abs(parse_centavos(r0[13])), "vat": "none", "withholding": atc if not (vat_goods or vat_svcs) else None, "noWithholding": None if (atc and not (vat_goods or vat_svcs)) else no_wh_reason, "purchaseType": "other_goods"})

        net_c = total_base or abs(parse_centavos(r0[13]))
        tot_c = net_c + in_vat
        pay_c = max(0, tot_c - ewt)
        b = Bill(
            status="void" if is_void else "recorded",
            supplier_id=sup.id,
            bill_number=(r0[6].strip() or doc_no)[:60],
            bill_date=b_dt,
            due_date=b_dt,
            po_number=(r0[6].strip()[:60] if r0[6].strip().startswith("PO") else None),
            oojeema_ref=doc_no[:60],
            notes=r0[4].strip()[:500] or None,
            amounts_include_vat=False,
            lines=b_lines,
            tax_reviewed=True,
            net_centavos=net_c,
            vat_centavos=in_vat,
            withheld_centavos=ewt,
            total_centavos=tot_c,
            payable_centavos=pay_c,
            paid_centavos=0,
            payables_account_id=ls.payables_account_id,
            entry_id=gl_entries.get(doc_no),
            created_by=imported_by,
            recorded_at=now,
            recorded_by=imported_by,
            approved_by=imported_by,
            approved_at=now,
            checked_by=imported_by if ewt > 0 else None,
            checked_at=now if ewt > 0 else None,
            voided_at=now if is_void else None,
            voided_by=imported_by if is_void else None,
            void_reason="Cancelled in Oojeema Purchase Journal" if is_void else None,
        )
        db.add(b)
        bills_by_ref[doc_no] = b
        q1_bills_added += 1

    er_rows = _csv_rows(expense_register_csv)
    er_hdr = next(i for i, r in enumerate(er_rows) if r and r[0].strip() == "Date")
    er_added = 0
    for r in er_rows[er_hdr + 1:]:
        if len(r) < 12:
            continue
        if not r[0].strip() or r[0].strip().lower().startswith("total"):
            continue
        exp_no = r[1].strip()
        if not exp_no or exp_no in bills_by_ref:
            continue
        is_void = r[11].strip().upper() == "CANCELLED"
        b_dt = parse_oojeema_date(r[0])
        sup = _get_supplier(r[2])
        net_c = abs(parse_centavos(r[7]))
        vat_c = abs(parse_centavos(r[8]))
        tot_c = abs(parse_centavos(r[9])) or (net_c + vat_c)
        bal_due = abs(parse_centavos(r[10]))
        no_wh_reason = "foreign" if sup.origin == "foreign" else "not_covered"
        b = Bill(
            status="void" if is_void else "recorded",
            supplier_id=sup.id,
            bill_number=(r[3].strip() or exp_no)[:60],
            bill_date=b_dt,
            due_date=b_dt,
            po_number=r[5].strip()[:60] or None,
            dr_number=r[4].strip()[:60] or None,
            oojeema_ref=exp_no[:60],
            notes=r[6].strip()[:500] or None,
            amounts_include_vat=False,
            lines=[{"accountId": expense_default_id, "description": r[6].strip()[:200] or "Expense", "amountCentavos": net_c, "vat": "vat" if vat_c > 0 else "none", "withholding": None, "noWithholding": no_wh_reason, "purchaseType": "services"}],
            tax_reviewed=True,
            net_centavos=net_c,
            vat_centavos=vat_c,
            withheld_centavos=0,
            total_centavos=tot_c,
            payable_centavos=tot_c,
            paid_centavos=0 if is_void else max(0, tot_c - bal_due),
            payables_account_id=ls.payables_account_id,
            entry_id=gl_entries.get(exp_no),
            created_by=imported_by,
            recorded_at=now,
            recorded_by=imported_by,
            approved_by=imported_by,
            approved_at=now,
            voided_at=now if is_void else None,
            voided_by=imported_by if is_void else None,
            void_reason="Cancelled in Oojeema Expense Register" if is_void else None,
        )
        db.add(b)
        bills_by_ref[exp_no] = b
        er_added += 1
    db.flush()

    existing_pvs = {v.number for v in db.scalars(select(PaymentVoucher))}
    dj_rows = _csv_rows(disbursement_journal_csv)
    dj_hdr = next(i for i, r in enumerate(dj_rows) if r and r[0].strip() == "Transaction Date")
    dj_live: list[list[str]] = []
    for r in dj_rows[dj_hdr + 1:]:
        if len(r) < 14:
            continue
        if not r[0].strip() or r[0].strip().lower().startswith("total"):
            continue
        ap_dr = parse_centavos(r[10])
        if ap_dr < 0:
            for idx, prev in enumerate(dj_live):
                if prev[8].strip() == r[8].strip() and parse_centavos(prev[10]) == -ap_dr:
                    dj_live.pop(idx)
                    break
            continue
        if ap_dr > 0 or parse_centavos(r[11]) > 0 or parse_centavos(r[12]) > 0:
            dj_live.append(r)

    pv_grouped: dict[str, list[list[str]]] = {}
    for r in dj_live:
        pv_no = r[8].strip() or r[7].strip() or f"PV-{len(pv_grouped)+1}"
        pv_grouped.setdefault(pv_no, []).append(r)

    vouchers_added = 0
    for pv_no, grp in pv_grouped.items():
        if pv_no[:20] in existing_pvs:
            continue
        r0 = grp[0]
        dt = parse_oojeema_date(r0[0])
        sup = _get_supplier(r0[1], r0[3], r0[2])
        tot_cash = sum(max(0, parse_centavos(x[11])) for x in grp)
        tot_chk = sum(max(0, parse_centavos(x[12])) for x in grp)
        tot_cc = sum(max(0, parse_centavos(x[13])) for x in grp)
        tot = tot_cash + tot_chk + tot_cc
        if tot <= 0:
            continue
        pv = PaymentVoucher(
            number=pv_no[:20],
            status="released",
            supplier_id=sup.id,
            method="check" if tot_chk > 0 else "bank",
            paid_from_id=ls.bank_account_id or ls.cash_account_id,
            total_centavos=tot,
            oojeema_ref=(r0[7].strip() or pv_no)[:60],
            notes=", ".join(dict.fromkeys(x[5].strip() for x in grp if x[5].strip()))[:500] or None,
            prepared_by=imported_by,
            released_by=imported_by,
            paid_on=dt,
            check_number=r0[4].strip()[:40] or None,
            check_date=dt if r0[4].strip() else None,
            entry_id=gl_entries.get(pv_no),
        )
        db.add(pv)
        db.flush()
        existing_pvs.add(pv.number)
        for pos_idx, x in enumerate(grp):
            line_amt = max(0, parse_centavos(x[11]) + parse_centavos(x[12]) + parse_centavos(x[13]))
            if line_amt <= 0:
                continue
            ref_key = x[6].strip() or x[5].strip()
            bill = bills_by_ref.get(ref_key)
            if bill is None:
                bill = Bill(
                    status="recorded",
                    supplier_id=sup.id,
                    bill_number=(ref_key or pv_no)[:60],
                    bill_date=date(2025, 12, 15),
                    due_date=dt,
                    oojeema_ref=(ref_key or pv_no)[:60],
                    amounts_include_vat=False,
                    lines=[{"accountId": expense_default_id, "description": "Prior Period Bill", "amountCentavos": line_amt, "vat": "none", "withholding": None, "noWithholding": "not_covered", "purchaseType": "other_goods"}],
                    tax_reviewed=True,
                    net_centavos=line_amt,
                    vat_centavos=0,
                    withheld_centavos=0,
                    total_centavos=line_amt,
                    payable_centavos=line_amt,
                    paid_centavos=0,
                    payables_account_id=ls.payables_account_id,
                    created_by=imported_by,
                    recorded_at=now,
                    recorded_by=imported_by,
                    approved_by=imported_by,
                    approved_at=now,
                )
                db.add(bill)
                db.flush()
                if ref_key:
                    bills_by_ref[ref_key] = bill
            db.add(VoucherLine(voucher_id=pv.id, bill_id=bill.id, position=pos_idx, amount_centavos=line_amt))
            bill.paid_centavos = min(bill.payable_centavos, bill.paid_centavos + line_amt)
        vouchers_added += 1

    for sup_id, counts in supplier_atc_counts.items():
        sup = db.get(Supplier, sup_id)
        if sup is not None and sup.origin != "foreign" and counts:
            best_atc = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
            sup.withholding = best_atc
            sup.tax_defaults_confirmed = True
            if "VILLAFLOR" in sup.name.upper():
                sup.withholding = "WC011"
                if not sup.email:
                    sup.email = "afvillaflorcustomsbrokerage@eyp.ph"
                if not sup.contacts:
                    sup.contacts = [{"salutation": "Mr.", "firstName": "Armenio", "lastName": "Villaflor", "designation": "General Manager", "email": "afvillaflorcustomsbrokerage@eyp.ph", "phone": "8332346"}]

    reconcile_operational_account_links(db)
    db.flush()
    return {
        "suppliersAdded": suppliers_added,
        "openingArInvoices": ar_added,
        "q1SalesInvoices": q1_invoices_added,
        "customerPayments": payments_added,
        "openingApBills": ap_added,
        "q1PurchaseBills": q1_bills_added,
        "q1ExpenseBills": er_added,
        "paymentVouchers": vouchers_added,
    }


def reconcile_operational_account_links(db: Session) -> dict:
    """Connect operational Bills, Payment Vouchers, Customer Payments, and Bank Accounts
    to their exact General Ledger destination accounts (no raw bank numbers stored)."""
    by_code = {a.code: a for a in db.scalars(select(Account))}
    acc_by_id = {a.id: a for a in by_code.values()}

    # 1. Ensure BankAccount records exist for active 2MG bank/e-wallet ledger accounts
    existing_banks = {b.account_id: b for b in db.scalars(select(BankAccount))}
    bank_specs = [
        ("1215-2MG", "bank", "bdo", "BDO Unibank (2MG)", "PHP", True),
        ("1216-2MG", "bank", "bpi", "BPI (2MG)", "PHP", False),
        ("1217-2MG", "bank", "eastwest", "EastWest Bank (2MG)", "PHP", False),
        ("1219-2MG", "bank", "landbank", "LANDBANK Link-Biz (2MG)", "PHP", False),
        ("0001-005", "bank", "landbank", "LANDBANK (Collections)", "PHP", False),
        ("0001-003", "bank", "eastwest", "EastWest Bank (USD)", "USD", False),
        ("0001-001", "bank", "other", "Maybank", "PHP", False),
        ("0001-008", "ewallet", "gcash", "GCash QR", "PHP", True),
    ]
    banks_added = 0
    for code, kind, provider, label, curr, is_def in bank_specs:
        acc = by_code.get(code)
        if acc is not None and acc.id not in existing_banks:
            if not acc.is_active:
                acc.is_active = True
            b = BankAccount(
                kind=kind,
                provider=provider,
                name=label,
                account_name="2MG INCORPORATED",
                account_number=None,
                currency=curr,
                account_id=acc.id,
                is_default=is_def,
                is_active=True,
            )
            db.add(b)
            db.flush()
            existing_banks[acc.id] = b
            banks_added += 1

    tax_codes = {
        "1600-000", "1601-000", "1602-000", "1603-000", "1607-000",
        "2300", "2301-000", "2302-000", "2303-000", "2304-000",
        "2305-000", "2306-000", "2307-000", "2307-100", "1507-000",
    }
    ap_codes = {"2101-000", "2102-000", "0009-000", "2000", "2100-000"}

    # 2. Connect Bill lines and payables_account_id to their exact GL journal lines
    bills_linked = 0
    for bill in db.scalars(select(Bill).where(Bill.entry_id.is_not(None))):
        jlines = db.scalars(select(JournalLine).where(JournalLine.entry_id == bill.entry_id)).all()
        dr_accs = [
            (ln.account_id, ln.debit_centavos)
            for ln in jlines
            if ln.debit_centavos > 0 and acc_by_id.get(ln.account_id) and acc_by_id[ln.account_id].code not in tax_codes
        ]
        cr_ap = [
            (ln.account_id, ln.credit_centavos)
            for ln in jlines
            if ln.credit_centavos > 0 and acc_by_id.get(ln.account_id) and acc_by_id[ln.account_id].code in ap_codes
        ]
        changed = False
        if dr_accs and bill.lines:
            best_dr_id = max(dr_accs, key=lambda x: x[1])[0]
            new_lines = []
            for ln in bill.lines:
                nl = dict(ln)
                nl["accountId"] = best_dr_id
                new_lines.append(nl)
            bill.lines = new_lines
            changed = True
        if cr_ap:
            bill.payables_account_id = max(cr_ap, key=lambda x: x[1])[0]
            changed = True
        if changed:
            bills_linked += 1

    # 3. Connect Payment Vouchers to the exact bank/cash account credited in their GL entry
    pvs_linked = 0
    for pv in db.scalars(select(PaymentVoucher).where(PaymentVoucher.entry_id.is_not(None))):
        jlines = db.scalars(select(JournalLine).where(JournalLine.entry_id == pv.entry_id)).all()
        cr_money = [
            (ln.account_id, ln.credit_centavos)
            for ln in jlines
            if ln.credit_centavos > 0 and acc_by_id.get(ln.account_id) and acc_by_id[ln.account_id].code not in tax_codes
        ]
        if cr_money:
            pv.paid_from_id = max(cr_money, key=lambda x: x[1])[0]
            pvs_linked += 1

    # 4. Connect Customer Invoice Payments to the exact BankAccount debited in their GL entry
    payments_linked = 0
    for pay in db.scalars(select(InvoicePayment).where(InvoicePayment.entry_id.is_not(None))):
        jlines = db.scalars(select(JournalLine).where(JournalLine.entry_id == pay.entry_id)).all()
        dr_banks = [
            (existing_banks[ln.account_id].id, ln.debit_centavos)
            for ln in jlines
            if ln.debit_centavos > 0 and ln.account_id in existing_banks
        ]
        if dr_banks:
            pay.bank_account_id = max(dr_banks, key=lambda x: x[1])[0]
            payments_linked += 1

    db.flush()
    return {
        "banksAdded": banks_added,
        "billsLinkedToTrueGlAccounts": bills_linked,
        "vouchersLinkedToTrueGlAccounts": pvs_linked,
        "customerPaymentsLinkedToBank": payments_linked,
    }
