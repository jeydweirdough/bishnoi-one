"""Finance's books as spreadsheets: the journal, one account's statement, the
trial balance and the fund requests, as CSV files Excel opens.

Read-only. Each file is built from the very answer its screen shows
(app/routers/ledger.py, app/routers/funds.py), so a file and its screen
always agree. Anyone signed in to Finance can download them, as they can see
the screens.

Amounts are plain numbers (1234.50, -500.00), so a spreadsheet can add them
up; words that a spreadsheet would run as a formula are made plain text.
"""

import csv
import io
from collections.abc import Iterable
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app.models import JournalEntry
from app.routers.funds import Task, list_requests, today
from app.routers.ledger import TYPE_LABELS, account_ledger, list_entries, trial_balance

router = APIRouter(prefix="/finance/exports", tags=["exports"])

# A file holds everything asked for, up to this many rows (the screens stop at 200).
MAX_ROWS = 50_000
# A spreadsheet runs a cell that starts with one of these as a formula.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def text(value: object) -> str:
    """A cell of words. One that would start a formula is shown as typed."""
    if value is None:
        return ""
    value = str(value)
    return "'" + value if value.startswith(FORMULA_START) else value


def money(settings: Settings, centavos: int | None) -> str:
    """1234.50: exact, whatever the size (no float), and never mistaken for a formula."""
    if centavos is None:
        return ""
    units = settings.org_minor_units
    whole, part = divmod(abs(centavos), 10**units)
    sign = "-" if centavos < 0 else ""
    return f"{sign}{whole}.{part:0{units}d}" if units else f"{sign}{whole}"


def side(settings: Settings, centavos: int) -> str:
    """A debit or credit column: empty on the side a line isn't on."""
    return money(settings, centavos) if centavos else ""


def local_day(settings: Settings, moment: str | None) -> str:
    """An ISO time from the API, as the company's calendar day."""
    if not moment:
        return ""
    return datetime.fromisoformat(moment).astimezone(ZoneInfo(settings.org_timezone)).date().isoformat()


def csv_file(name: str, header: list[str], rows: Iterable[list[str]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    # The byte-order mark tells Excel the file is UTF-8, so ₱, ñ and › show as they are.
    return Response("﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}"'})


def span(since: date | None, until: date) -> str:
    return f"{since.isoformat()}-to-{until.isoformat()}" if since else f"to-{until.isoformat()}"


# --- the ledger --------------------------------------------------------------------------------


@router.get("/journal.csv")
def journal(
    user: CurrentUser,
    db: DB,
    settings: SettingsDep,
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
    source: Literal["manual", "fund"] | None = None,
    q: str | None = Query(None, max_length=100),
) -> Response:
    """Every line of every entry asked for, oldest first: the general journal."""
    entries = list(reversed(list_entries(user=user, db=db, since=since, until=until, source=source, q=q, limit=MAX_ROWS)["items"]))
    reversed_by = {e["reversedById"] for e in entries if e["reversedById"]}
    numbers = dict(db.execute(select(JournalEntry.id, JournalEntry.number).where(JournalEntry.id.in_(reversed_by))).all()) if reversed_by else {}
    rows = (
        [
            e["date"], e["number"], text(e["memo"]), text(e["reference"]), "Fund request" if e["source"] == "fund" else "Manual",
            text(ln["account"]["code"]), text(ln["account"]["name"]), text(ln["description"]),
            side(settings, ln["debitCentavos"]), side(settings, ln["creditCentavos"]),
            text(e["postedBy"]), numbers.get(e["reversedById"], ""),
        ]
        for e in entries
        for ln in e["lines"]
    )
    header = ["Date", "Entry", "Memo", "Reference", "Source", "Account code", "Account", "Line description", "Debit", "Credit", "Posted by", "Reversed by"]
    return csv_file(f"journal-{span(since, until or today(settings))}.csv", header, rows)


@router.get("/accounts/{account_id}/statement.csv")
def statement(
    user: CurrentUser,
    db: DB,
    settings: SettingsDep,
    account_id: str,
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
) -> Response:
    """One account's lines with the balance after each, between the balance
    brought forward and the closing balance."""
    ledger = account_ledger(user=user, db=db, account_id=account_id, since=since, until=until)
    a = ledger["account"]
    rows = [["", "", "Balance brought forward", "", "", "", money(settings, ledger["openingCentavos"])]]
    rows += [
        [
            ln["date"], ln["number"], text(ln["memo"]), text(ln["description"]),
            side(settings, ln["debitCentavos"]), side(settings, ln["creditCentavos"]), money(settings, ln["balanceCentavos"]),
        ]
        for ln in ledger["lines"]
    ]
    rows.append(["", "", "Closing balance", "", "", "", money(settings, ledger["closingCentavos"])])
    header = ["Date", "Entry", "Memo", "Line description", "Debit", "Credit", "Balance"]
    return csv_file(f"account-{a['code']}-{span(since, until or today(settings))}.csv", header, rows)


@router.get("/trial-balance.csv")
def trial_balance_file(user: CurrentUser, db: DB, settings: SettingsDep, until: date | None = Query(None, alias="to")) -> Response:
    tb = trial_balance(user=user, db=db, settings=settings, until=until)
    rows = [
        [
            text(r["account"]["code"]), text(r["account"]["name"]), TYPE_LABELS[r["account"]["type"]],
            side(settings, r["debitCentavos"]), side(settings, r["creditCentavos"]),
        ]
        for r in tb["rows"]
    ]
    rows.append(["", "Total", "", money(settings, tb["debitCentavos"]), money(settings, tb["creditCentavos"])])
    return csv_file(f"trial-balance-{tb['to']}.csv", ["Code", "Account", "Type", "Debit", "Credit"], rows)


# --- fund requests -------------------------------------------------------------------------------


@router.get("/funds.csv")
def funds(user: CurrentUser, db: DB, settings: SettingsDep, task: Task = "all", q: str | None = Query(None, max_length=100)) -> Response:
    """The fund requests on one of Finance's lists (all of them by default):
    what was asked, approved, released, spent and settled."""
    items = list_requests(user=user, db=db, settings=settings, task=task, q=q, limit=MAX_ROWS)["items"]
    rows = []
    for r in items:
        release, t = r["release"] or {}, r["tally"]
        # Spending only means something once there's money out to spend.
        spent = bool(release) and r["liquidate"]
        rows.append([
            text(r["number"]), r["statusLabel"], "Yes" if r["overdue"] else "",
            text(r["requester"]["name"]), text(r["requester"]["email"]), text(r["requester"]["team"]),
            text(r["purpose"]), text(r["customerName"]), r["neededOn"] or "", "Yes" if r["liquidate"] else "No",
            money(settings, r["requestedCentavos"]), money(settings, r["approvedCentavos"]),
            text(r["approval"]["by"]), local_day(settings, r["approval"]["at"]),
            money(settings, release.get("amountCentavos")), release.get("methodLabel") or "", text(release.get("reference")),
            local_day(settings, release.get("at")), release.get("liquidateBy") or "",
            money(settings, t["spentCentavos"]) if spent else "", money(settings, t["coveredCentavos"]) if spent else "",
            money(settings, r["returnDueCentavos"]), money(settings, r["returnedCentavos"]),
            money(settings, r["reimburseDueCentavos"]), money(settings, r["reimbursedCentavos"]),
            local_day(settings, r["closedAt"]), text(r["cancelReason"]),
        ])
    header = [
        "Number", "Status", "Overdue", "Requester", "Email", "Team", "Purpose", "Customer", "Needed on", "Subject to liquidation",
        "Requested", "Approved", "Approved by", "Approved on", "Released", "Release method", "Release reference", "Released on",
        "Liquidation due", "Total expenses", "Charged to company", "Refund due", "Refund received", "Reimbursement due",
        "Reimbursement paid", "Closed on", "Cancel reason",
    ]
    return csv_file(f"fund-requests-{task.replace('_', '-')}-{today(settings).isoformat()}.csv", header, rows)
