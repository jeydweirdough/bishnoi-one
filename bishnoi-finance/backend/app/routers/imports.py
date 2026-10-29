"""Import matching (Settings → Import matching) and importing Zoho bills and supplier payments.

Matching: someone with "Propose matches" loads the Zoho Bills and Vendor Payments exports; each
label they use is saved once (app/zoho_import.py). They propose Finance's choice for it; someone
else confirms it (tax labels: BIR and Compliance). Only confirmed matches are used.

Importing: preview first, then import exactly what the preview showed. For now only on the
testing site: Q1 2026 is the historical test basis, not official opening figures (Decisions,
2026-10-27); official imports come with the cut-off plan, under their own approval.
"""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.access import access_of
from app.api import Api
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.import_review import norm
from app.models import Account, ImportMatch, ImportRule, ImportRun
from app.payables import PURCHASE_TYPES, VAT_KINDS
from app import zoho_import as zi

router = APIRouter(prefix="/finance/imports", tags=["Imports"])

TICKS = ("imports.propose", "imports.confirm", "imports.confirm_tax", "imports.run")


class File(Api):
    name: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=8 * 1024 * 1024)


class Files(Api):
    files: list[File] = Field(min_length=2, max_length=2)


class Run(Files):
    plan_key: str = Field(min_length=64, max_length=64)


class Proposal(Api):
    account_id: str | None = Field(None, max_length=36)
    purchase_type: Literal["services", "capital_goods", "other_goods", "importation"] | None = None
    vat_kind: Literal["vat", "zero", "exempt", "none"] | None = None
    company: Literal["2mg", "gpi"] | None = None
    note: str | None = Field(None, max_length=300)
    # Accounts and tax labels only: no default; each line takes a supplier rule or its own choice.
    per_record: bool = False


class RuleIn(Api):
    """For all lines from one supplier, or for one line of one bill (as the records window shows it)."""
    scope: Literal["supplier", "line"]
    supplier: str = Field(min_length=1, max_length=200)
    bill_source_id: str | None = Field(None, max_length=120)
    bill_number: str | None = Field(None, max_length=60)
    line_position: int | None = Field(None, ge=1, le=1000)
    line_amount_centavos: int | None = None
    account_id: str | None = Field(None, max_length=36)
    purchase_type: Literal["services", "capital_goods", "other_goods", "importation"] | None = None
    vat_kind: Literal["vat", "zero", "exempt", "none"] | None = None
    note: str | None = Field(None, max_length=300)


def need(user, *ticks: str) -> None:
    can = access_of(user).can
    if not any(can(t) for t in ticks):
        raise HTTPException(403, "Your role can't use import matching. Ask the administrator for the Imports permissions.")


def files_of(body: Files) -> list[dict]:
    return [f.model_dump() for f in body.files]


def pack(body: Files) -> list[dict]:
    try:
        return zi.read_pack(files_of(body))
    except zi.PackError as error:
        raise HTTPException(422, str(error)) from None


def match_out(m: ImportMatch, user) -> dict:
    can = access_of(user).can
    mine = m.proposed_by_id == user.id
    return {
        "id": m.id, "section": m.section, "sourceLabel": m.source_label, "sourceCode": m.source_code,
        "records": m.records, "amountCentavos": m.amount_centavos, "status": m.status, "note": m.note,
        "accountId": m.account_id, "account": {"id": m.account.id, "code": m.account.code, "name": m.account.name} if m.account else None,
        "purchaseType": m.purchase_type, "vatKind": m.vat_kind, "company": m.company,
        "proposedBy": m.proposed_by, "proposedAt": m.proposed_at.isoformat() if m.proposed_at else None,
        "confirmedBy": m.confirmed_by, "confirmedAt": m.confirmed_at.isoformat() if m.confirmed_at else None,
        "seenAt": m.seen_at.isoformat() if m.seen_at else None,
        "canPropose": can("imports.propose") or can(zi.CONFIRMS[m.section]),
        # Saving confirms it at once for someone who may confirm this section.
        "savesConfirmed": can(zi.CONFIRMS[m.section]),
        "automatic": m.confirmed_by == zi.AUTOMATIC,
        "canConfirm": m.status == "proposed" and can(zi.CONFIRMS[m.section]) and not mine,
        # Who it waits on, as the row shows it.
        "waitingOn": None if m.status == "confirmed" else ("BIR and Compliance" if m.section == "tax" else "Finance Head (or the deputy)") if m.status == "proposed" else "a proposal",
        "mine": mine,
        "perRecord": m.per_record,
        "rules": {k: sum(1 for r in m.rules if r.status == k) for k in ("proposed", "confirmed")},
    }


def rule_out(r: ImportRule, user) -> dict:
    can = access_of(user).can
    section = r.match.section
    return {
        "id": r.id, "scope": r.scope, "supplier": r.supplier, "billSourceId": r.bill_source_id, "billNumber": r.bill_number,
        "linePosition": r.line_position, "lineAmountCentavos": r.line_amount_centavos,
        "accountId": r.account_id, "account": {"id": r.account.id, "code": r.account.code, "name": r.account.name} if r.account else None,
        "purchaseType": r.purchase_type, "vatKind": r.vat_kind, "status": r.status, "note": r.note,
        "proposedBy": r.proposed_by, "proposedAt": r.proposed_at.isoformat() if r.proposed_at else None,
        "confirmedBy": r.confirmed_by, "confirmedAt": r.confirmed_at.isoformat() if r.confirmed_at else None,
        "canConfirm": r.status == "proposed" and can(zi.CONFIRMS[section]) and r.proposed_by_id != user.id,
        "canRemove": can(zi.CONFIRMS[section]) or (can("imports.propose") and r.status == "proposed"),
    }


@router.get("/matching")
def list_matches(user: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    need(user, *TICKS)
    from app.routers.vouchers import paying_accounts

    rows = list(db.scalars(select(ImportMatch).where(ImportMatch.source == zi.SOURCE).order_by(ImportMatch.section, ImportMatch.amount_centavos.desc(), ImportMatch.source_label)))
    lines = sorted(zi.posting_accounts(db).values(), key=lambda a: a.code)
    can = access_of(user).can
    return {
        "matches": [match_out(m, user) for m in rows],
        "counts": {s: {k: sum(1 for m in rows if m.section == s and m.status == k) for k in ("open", "proposed", "confirmed")} for s in zi.SECTIONS},
        "choices": {
            "lineAccounts": [{"id": a.id, "code": a.code, "name": a.name, "type": a.type} for a in lines],
            "moneyAccounts": [{"id": a.id, "code": a.code, "name": a.name} for a in paying_accounts(db)],
            "purchaseTypes": [{"key": k, "label": v} for k, v in PURCHASE_TYPES.items()],
            "vatKinds": [{"key": k, "label": v} for k, v in VAT_KINDS.items()],
            "companies": [{"key": k, "label": v} for k, v in zi.COMPANIES.items()],
        },
        "may": {t.split(".")[1]: can(t) for t in TICKS},
        "importsHere": settings.data_environment == "local_test",
        "runs": [{"id": r.id, "kind": r.kind, "files": r.files, "counts": r.counts, "by": r.created_by, "at": r.created_at.isoformat()}
                 for r in db.scalars(select(ImportRun).order_by(ImportRun.created_at.desc()).limit(10))],
    }


@router.post("/matching/load")
def load(user: CurrentUser, db: DB, body: Files) -> dict:
    need(user, "imports.propose")
    docs = pack(body)
    try:
        out = zi.load_groups(db, docs, user)
    except zi.PackError as error:
        raise HTTPException(422, str(error)) from None
    db.commit()
    return out


def found(db, match_id: str) -> ImportMatch:
    m = db.get(ImportMatch, match_id)
    if m is None or m.source != zi.SOURCE:
        raise HTTPException(404, "There's no such match.")
    return m


@router.post("/matching/{match_id}/records")
def match_records(user: CurrentUser, db: DB, match_id: str, body: Files) -> dict:
    """The records behind one label, read from the exports sent (they aren't stored). Saves nothing."""
    need(user, *TICKS)
    m = found(db, match_id)
    return zi.records_for(db, pack(body), m)


@router.put("/matching/{match_id}")
def propose(user: CurrentUser, db: DB, match_id: str, body: Proposal) -> dict:
    """Saved by someone who may confirm this section: confirmed at once (one step, changed 2026-10-29
    at the user's ask). Saved by someone who may only propose: it waits for someone who may confirm."""
    m = found(db, match_id)
    sure = access_of(user).can(zi.CONFIRMS[m.section])
    if not sure:
        need(user, "imports.propose")
    if m.section == "company":
        if not body.company:
            raise HTTPException(422, "Choose the company.")
        m.account_id = m.purchase_type = m.vat_kind = None
        m.company = body.company
    elif m.section == "tax":
        if not body.vat_kind and not body.per_record:
            raise HTTPException(422, "Choose the VAT kind, or mark it as depending on the record.")
        m.account_id = m.purchase_type = m.company = None
        m.vat_kind = None if body.per_record else body.vat_kind
    elif m.section == "account":
        if not body.per_record and (body.account_id not in zi.posting_accounts(db) or not body.purchase_type):
            raise HTTPException(422, "Choose an active expense or asset account and the purchase type, or mark it as depending on the record.")
        m.vat_kind = m.company = None
        m.account_id, m.purchase_type = (None, None) if body.per_record else (body.account_id, body.purchase_type)
    else:
        from app.routers.vouchers import paying_accounts
        if body.account_id not in {a.id for a in paying_accounts(db)}:
            raise HTTPException(422, "Choose one of the accounts money is paid from (under CASH).")
        m.purchase_type = m.vat_kind = m.company = None
        m.account_id = body.account_id
    m.per_record = body.per_record and m.section in ("account", "tax")
    m.note = (body.note or "").strip() or None
    now = datetime.now(UTC)
    m.status, m.proposed_by, m.proposed_by_id, m.proposed_at = "confirmed" if sure else "proposed", user.full_name[:120], user.id, now
    m.confirmed_by, m.confirmed_by_id, m.confirmed_at = (user.full_name[:120], user.id, now) if sure else (None, None, None)
    audit(db, user, "imports.match_confirmed" if sure else "imports.match_proposed", target=m.source_label[:200] or "(blank)", target_type="import_match", target_id=m.id,
          fields=["account_id", "purchase_type", "vat_kind", "company", "per_record"])
    db.commit()
    db.refresh(m)
    return match_out(m, user)


@router.post("/matching/{match_id}/confirm")
def confirm(user: CurrentUser, db: DB, match_id: str) -> dict:
    m = found(db, match_id)
    need(user, zi.CONFIRMS[m.section])
    if m.status != "proposed":
        raise HTTPException(409, "This match isn't waiting for confirmation. Reload to see where it stands.")
    if m.proposed_by_id == user.id:
        raise HTTPException(403, "You proposed this match, so someone else confirms it.")
    if m.account_id and db.get(Account, m.account_id) is None:
        raise HTTPException(409, "The proposed account no longer exists. Propose again.")
    m.status, m.confirmed_by, m.confirmed_by_id, m.confirmed_at = "confirmed", user.full_name[:120], user.id, datetime.now(UTC)
    audit(db, user, "imports.match_confirmed", target=m.source_label[:200] or "(blank)", target_type="import_match", target_id=m.id)
    db.commit()
    db.refresh(m)
    return match_out(m, user)


@router.get("/matching/{match_id}/rules")
def list_rules(user: CurrentUser, db: DB, match_id: str) -> dict:
    need(user, *TICKS)
    m = found(db, match_id)
    order = {"supplier": 0, "line": 1}
    return {"rules": [rule_out(r, user) for r in sorted(m.rules, key=lambda r: (order[r.scope], r.supplier, r.bill_number or "", r.line_position or 0))]}


@router.post("/matching/{match_id}/rules")
def save_rule(user: CurrentUser, db: DB, match_id: str, body: RuleIn) -> dict:
    """Saved by someone who may confirm the section: final at once; otherwise it waits (as for labels).
    Saving again for the same supplier or line replaces the earlier choice."""
    m = found(db, match_id)
    if m.section not in ("account", "tax"):
        raise HTTPException(422, "Supplier rules and line choices are for bill-line accounts and tax labels.")
    sure = access_of(user).can(zi.CONFIRMS[m.section])
    if not sure:
        need(user, "imports.propose")
    if m.section == "account":
        if body.account_id is None and body.purchase_type is None:
            raise HTTPException(422, "Choose the account, the purchase type, or both.")
        if body.account_id is not None and body.account_id not in zi.posting_accounts(db):
            raise HTTPException(422, "Choose an active expense or asset account.")
        if body.vat_kind is not None:
            raise HTTPException(422, "A VAT kind is chosen under Tax labels.")
    elif body.vat_kind is None or body.account_id is not None or body.purchase_type is not None:
        raise HTTPException(422, "Choose the VAT kind for these lines.")
    if body.scope == "line" and not (body.bill_source_id and body.line_position and body.line_amount_centavos is not None):
        raise HTTPException(422, "A line choice needs the bill, the line and its amount, as the records window gives them.")
    key = norm(body.supplier)
    if body.scope == "supplier":
        r = next((x for x in m.rules if x.scope == "supplier" and x.supplier_key == key), None)
    else:
        r = next((x for x in m.rules if x.scope == "line" and x.bill_source_id == body.bill_source_id and x.line_position == body.line_position), None)
    now = datetime.now(UTC)
    if r is None:
        r = ImportRule(match=m, scope=body.scope, supplier=body.supplier.strip()[:200], supplier_key=key[:200], proposed_by=user.full_name[:120])
        db.add(r)
    if body.scope == "line":
        r.bill_source_id, r.bill_number, r.line_position, r.line_amount_centavos = body.bill_source_id, body.bill_number, body.line_position, body.line_amount_centavos
    r.account_id, r.purchase_type, r.vat_kind = body.account_id, body.purchase_type, body.vat_kind
    r.note = (body.note or "").strip() or None
    r.status, r.proposed_by, r.proposed_by_id, r.proposed_at = "confirmed" if sure else "proposed", user.full_name[:120], user.id, now
    r.confirmed_by, r.confirmed_by_id, r.confirmed_at = (user.full_name[:120], user.id, now) if sure else (None, None, None)
    db.flush()
    audit(db, user, "imports.rule_confirmed" if sure else "imports.rule_proposed", target=f"{m.source_label or '(blank)'}: {r.supplier}"[:200],
          target_type="import_rule", target_id=r.id, fields=["account_id", "purchase_type", "vat_kind"])
    db.commit()
    db.refresh(r)
    return rule_out(r, user)


def found_rule(db, rule_id: str) -> ImportRule:
    r = db.get(ImportRule, rule_id)
    if r is None:
        raise HTTPException(404, "There's no such rule.")
    return r


@router.post("/rules/{rule_id}/confirm")
def confirm_rule(user: CurrentUser, db: DB, rule_id: str) -> dict:
    r = found_rule(db, rule_id)
    need(user, zi.CONFIRMS[r.match.section])
    if r.status != "proposed":
        raise HTTPException(409, "This choice isn't waiting for confirmation. Reload to see where it stands.")
    if r.proposed_by_id == user.id:
        raise HTTPException(403, "You proposed this choice, so someone else confirms it.")
    r.status, r.confirmed_by, r.confirmed_by_id, r.confirmed_at = "confirmed", user.full_name[:120], user.id, datetime.now(UTC)
    audit(db, user, "imports.rule_confirmed", target=f"{r.match.source_label or '(blank)'}: {r.supplier}"[:200], target_type="import_rule", target_id=r.id)
    db.commit()
    db.refresh(r)
    return rule_out(r, user)


@router.delete("/rules/{rule_id}")
def remove_rule(user: CurrentUser, db: DB, rule_id: str) -> dict:
    """Those lines go back to the supplier rule or the label's default (or are held)."""
    r = found_rule(db, rule_id)
    if not rule_out(r, user)["canRemove"]:
        raise HTTPException(403, "Removing a confirmed choice needs permission to confirm this section.")
    audit(db, user, "imports.rule_removed", target=f"{r.match.source_label or '(blank)'}: {r.supplier}"[:200], target_type="import_rule", target_id=r.id)
    db.delete(r)
    db.commit()
    return {"removed": rule_id}


def testing_only(settings) -> None:
    if settings.data_environment != "local_test":
        raise HTTPException(409, "Q1 imports run on the testing site for now (Q1 is the test basis, not official opening figures). Nothing was changed here.")


def may_import(user, kind: str) -> None:
    need(user, "imports.run")
    view = "bills.view" if kind == "bills" else "vouchers.view"
    if not access_of(user).can(view):
        raise HTTPException(403, "Importing also needs permission to view them (bills or payment vouchers).")


def run_import(fn, db, settings, user, body):
    try:
        return fn(db, settings, user, files_of(body), body.plan_key)
    except zi.PackError as error:
        raise HTTPException(422, str(error)) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Some of these records were imported at the same moment by someone else. Nothing was saved from this run; preview again.") from None


@router.post("/bills/preview")
def preview_bills(user: CurrentUser, db: DB, settings: SettingsDep, body: Files) -> dict:
    testing_only(settings)
    may_import(user, "bills")
    rows = zi.plan_bills(db, pack(body), settings)
    return {**zi.summary(rows), "rows": zi.rows_out(rows)}


@router.post("/bills")
def import_bills(user: CurrentUser, db: DB, settings: SettingsDep, body: Run) -> dict:
    testing_only(settings)
    may_import(user, "bills")
    return run_import(zi.import_bills, db, settings, user, body)


@router.post("/supplier-payments/preview")
def preview_payments(user: CurrentUser, db: DB, settings: SettingsDep, body: Files) -> dict:
    testing_only(settings)
    may_import(user, "payments")
    rows = zi.plan_payments(db, pack(body), settings)
    return {**zi.summary(rows), "rows": zi.rows_out(rows)}


@router.post("/supplier-payments")
def import_payments(user: CurrentUser, db: DB, settings: SettingsDep, body: Run) -> dict:
    testing_only(settings)
    may_import(user, "payments")
    return run_import(zi.import_payments, db, settings, user, body)
