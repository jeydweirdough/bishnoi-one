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
from app.models import Account, ImportMatch, ImportRun
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
        if not body.vat_kind:
            raise HTTPException(422, "Choose the VAT kind.")
        m.account_id = m.purchase_type = m.company = None
        m.vat_kind = body.vat_kind
    elif m.section == "account":
        if body.account_id not in zi.posting_accounts(db) or not body.purchase_type:
            raise HTTPException(422, "Choose an active expense or asset account with nothing under it, and the purchase type.")
        m.vat_kind = m.company = None
        m.account_id, m.purchase_type = body.account_id, body.purchase_type
    else:
        from app.routers.vouchers import paying_accounts
        if body.account_id not in {a.id for a in paying_accounts(db)}:
            raise HTTPException(422, "Choose one of the accounts money is paid from (under CASH).")
        m.purchase_type = m.vat_kind = m.company = None
        m.account_id = body.account_id
    m.note = (body.note or "").strip() or None
    now = datetime.now(UTC)
    m.status, m.proposed_by, m.proposed_by_id, m.proposed_at = "confirmed" if sure else "proposed", user.full_name[:120], user.id, now
    m.confirmed_by, m.confirmed_by_id, m.confirmed_at = (user.full_name[:120], user.id, now) if sure else (None, None, None)
    audit(db, user, "imports.match_confirmed" if sure else "imports.match_proposed", target=m.source_label[:200] or "(blank)", target_type="import_match", target_id=m.id,
          fields=["account_id", "purchase_type", "vat_kind", "company"])
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
