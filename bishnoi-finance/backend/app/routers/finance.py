"""Finance's endpoints. Add them here, under /finance.

Anything that needs a signed-in person takes `user: CurrentUser` from
app.deps, or `user: permitted("<area>.<action>")` from app.access when it
needs a permission (app/permissions.py).

The Overview's dashboard (planned 2026-10-22): one page of sections, each sent
only to a role whose work it is, judged by what the role may *do*, not its name
(as the CRM's Home does), so a renamed or new role gets the sections its
permissions earn. The three starting roles (Administrator, Finance Staff,
Auditor) keep the Overview as it was. The CRM's waiting prices are their own
request (GET /finance/dashboard/waiting-prices), so the page never waits on
the CRM, and the answer is kept a minute.
"""

import time
from datetime import date

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import func, select, update

from app.access import CurrentAccess, permitted
from app.crm import CrmUnavailable, waiting_prices
from app.deps import DB, CurrentUser, SettingsDep
from app.models import FundRequest, Invoice, JournalEntry, JournalLine, Notification, utcnow
from app.notify import ACTIONABLE, GROUPS, unread_count
from app.permissions import ROLE_ADMIN_ID, ROLE_AUDITOR_ID, ROLE_STAFF_ID
from app.routers.tax import Api

router = APIRouter(prefix="/finance", tags=["finance"])

# The starting roles keep the Overview as it was (decided 2026-10-22: the new
# dashboard is for the roles made for the finance team, Malou's and Rommel's first).
KEEP_OVERVIEW = {ROLE_ADMIN_ID, ROLE_STAFF_ID, ROLE_AUDITOR_ID}
LATEST_ENTRIES = 5
TOP_CUSTOMERS = 5


def section_keys(access: CurrentAccess) -> list[str]:
    """The sections this person's work calls for, in the order they're shown."""
    can = access.can
    keys = []
    if can("prices.approve") or can("funds.check") or can("funds.release") or can("funds.settle") or can("journal.approve"):
        keys.append("waiting")
    if can("invoices.collect"):
        keys.append("receivables")
    if can("invoices.issue"):
        keys.append("sales")
    if can("funds.check") or can("funds.release"):
        keys.append("spending")
    if can("journal.post"):
        keys.append("journal")
    if can("tax.manage"):
        keys.append("tax")
    if can("accounts.view") and can("journal.view"):
        keys.append("cash")
    return keys


def waiting_section(access: CurrentAccess, db: DB, on: date) -> dict:
    """Cash advances to release, liquidations to review (not ones this person
    released: someone else reviews those), refunds and reimbursements to settle,
    and late liquidations. The CRM's prices come separately."""
    by = dict(db.execute(select(FundRequest.status, func.count()).group_by(FundRequest.status)).all())
    review = db.scalar(
        select(func.count()).where(
            FundRequest.status == "to_check",
            (FundRequest.released_by_id.is_(None)) | (FundRequest.released_by_id != access.user.id),
        )
    )
    overdue = db.scalar(select(func.count()).where(FundRequest.status == "to_liquidate", FundRequest.liquidate_by < on))
    # Journal entries this person may approve: waiting, and not their own.
    entries = db.scalar(
        select(func.count()).where(
            JournalEntry.status == "waiting",
            (JournalEntry.posted_by_id.is_(None)) | (JournalEntry.posted_by_id != access.user.id),
        )
    )
    return {
        "canApproveEntries": access.can("journal.approve"),
        "entriesToApprove": entries or 0,
        "canApprovePrices": access.can("prices.approve"),
        "canRelease": access.can("funds.release"),
        "toRelease": by.get("to_release", 0),
        "canReview": access.can("funds.check"),
        "toReview": review or 0,
        "canSettle": access.can("funds.settle"),
        "toSettle": by.get("to_return", 0) + by.get("to_reimburse", 0),
        "overdueLiquidations": overdue or 0,
    }


def receivables_section(db: DB, settings, on: date) -> dict:
    from app.routers.receivables import ageing

    found = ageing(None, db, settings, on)
    return {
        "totalCentavos": found["totalCentavos"],
        "buckets": found["buckets"],
        "customers": len(found["customers"]),
        "mostOverdue": [
            {"name": c["name"], "owedCentavos": c["totalCentavos"], "oldestDaysLate": c["oldestDaysLate"]}
            for c in found["customers"][:TOP_CUSTOMERS]
            if c["oldestDaysLate"] > 0
        ],
    }


def invoiced(db: DB, since: date, until: date) -> dict:
    """Issued invoices dated in [since, until]: how many, and for how much. Voided ones don't count."""
    count, total, tax = db.execute(
        select(func.count(), func.coalesce(func.sum(Invoice.total_centavos), 0), func.coalesce(func.sum(Invoice.tax_centavos), 0)).where(
            Invoice.status == "issued", Invoice.invoice_date >= since, Invoice.invoice_date <= until
        )
    ).one()
    return {"count": count, "totalCentavos": total, "taxCentavos": tax}


def sales_section(db: DB, on: date) -> dict:
    return {
        "month": invoiced(db, on.replace(day=1), on),
        "year": invoiced(db, on.replace(month=1, day=1), on),
    }


def spending_section(db: DB, on: date) -> dict:
    """Marketing spending by the team that asked: accepted receipts in
    categories the company covers, on liquidations already reviewed."""
    year_start, month_start = on.replace(month=1, day=1), on.replace(day=1)
    checked = db.scalars(select(FundRequest).where(FundRequest.checked_at.is_not(None))).all()
    teams: dict[str, dict] = {}
    for r in checked:
        for e in r.expenses:
            if e.accepted is not True or e.category is None or not e.category.covered or not (year_start <= e.spent_on <= on):
                continue
            t = teams.setdefault(r.team_name or "No team", {"team": r.team_name or "No team", "yearCentavos": 0, "monthCentavos": 0})
            t["yearCentavos"] += e.amount_centavos
            if e.spent_on >= month_start:
                t["monthCentavos"] += e.amount_centavos
    return {"teams": sorted(teams.values(), key=lambda t: -t["yearCentavos"])}


def journal_section(access: CurrentAccess, db: DB, on: date) -> dict:
    latest = db.scalars(select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(LATEST_ENTRIES)).all()
    # Only approved entries count in the books.
    debits, credits = db.execute(
        select(func.coalesce(func.sum(JournalLine.debit_centavos), 0), func.coalesce(func.sum(JournalLine.credit_centavos), 0))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalEntry.status == "approved")
    ).one()
    this_month = db.scalar(
        select(func.count()).where(JournalEntry.status == "approved", JournalEntry.entry_date >= on.replace(day=1), JournalEntry.entry_date <= on)
    )
    # The sender's side of the hand-off: what this person posted that's still waiting on someone else.
    mine_waiting = db.scalar(select(func.count()).where(JournalEntry.status == "waiting", JournalEntry.posted_by_id == access.user.id))
    return {
        "myWaiting": mine_waiting or 0,
        "latest": [
            {
                "id": e.id,
                "number": e.number,
                "date": e.entry_date.isoformat(),
                "memo": e.memo,
                "postedBy": e.posted_by,
                "source": e.source,
                "status": e.status,
                "totalCentavos": sum(ln.debit_centavos for ln in e.lines),
            }
            for e in latest
        ],
        "thisMonth": this_month or 0,
        "balanced": debits == credits,
    }


def tax_section(access: CurrentAccess, db: DB, on: date) -> dict:
    from app.routers.unset import unset

    first_month = 3 * ((on.month - 1) // 3) + 1
    quarter = invoiced(db, on.replace(month=first_month, day=1), on)
    return {
        "notSetUp": unset(access, db),
        "quarter": f"Q{(on.month - 1) // 3 + 1} {on.year}",
        "quarterInvoices": quarter["count"],
        "quarterTaxCentavos": quarter["taxCentavos"],
    }


@router.get("/dashboard")
def dashboard(access: CurrentAccess, db: DB, settings: SettingsDep) -> dict:
    """The Overview: the sections this person's role calls for, worked out from
    what Finance keeps (nothing is asked of another app here)."""
    from app.routers.funds import today

    if access.user.role_id in KEEP_OVERVIEW:
        return {"kept": True, "sections": []}
    on = today(settings)
    build = {
        "waiting": lambda: waiting_section(access, db, on),
        "receivables": lambda: receivables_section(db, settings, on),
        "sales": lambda: sales_section(db, on),
        "spending": lambda: spending_section(db, on),
        "journal": lambda: journal_section(access, db, on),
        "tax": lambda: tax_section(access, db, on),
        "cash": lambda: {},
    }
    return {"kept": False, "on": on.isoformat(), "sections": [{"key": k, **build[k]()} for k in section_keys(access)]}


# --- BIR files ----------------------------------------------------------------------------------


@router.get("/bir/sales-dat")
def sales_dat_setup(user: permitted("bir.prepare")) -> dict:
    """What the Sales DAT screen needs from the API: each company's details for the
    file (app/bir.py). The file itself is made in the browser; asking here is also
    what keeps the screen to a role that prepares BIR files."""
    from app.bir import companies_out

    return {"companies": companies_out()}


# --- the CRM's waiting prices, asked on their own and kept a minute ---------------------------

KEEP_FOR = 60  # seconds
_kept: dict = {}


def forget_waiting_prices() -> None:
    """For tests, and whenever an answer must not be reused."""
    _kept.clear()


@router.get("/dashboard/waiting-prices")
def dashboard_waiting_prices(user: permitted("prices.approve"), settings: SettingsDep) -> dict:
    """How many prices and quotes wait in the CRM for Finance. Kept KEEP_FOR
    seconds, so opening the Overview again doesn't ask again; a failure isn't
    kept, so the next visit tries again. The Prices screen itself always asks."""
    now = time.monotonic()
    if _kept and now - _kept["at"] < KEEP_FOR:
        return _kept["answer"]
    try:
        found = waiting_prices(settings)
    except CrmUnavailable as e:
        return {"available": False, "message": str(e)}
    answer = {"available": True, "prices": len(found.get("prices", [])), "quotes": len(found.get("quotes", []))}
    _kept.update(at=now, answer=answer)
    return answer


# --- notifications: the bell (app/notify.py makes them) -----------------------------------------

SHOWN = 30


def notification_out(n: Notification) -> dict:
    return {
        "id": n.id, "ids": [n.id], "kind": n.kind, "text": n.text, "link": n.link, "at": n.created_at.isoformat(),
        "read": n.read_at is not None, "counts": n.kind in ACTIONABLE,
    }


def grouped(latest: list[Notification]) -> list[dict]:
    """Several unread of a kind (app/notify.py GROUPS) become one line, where the newest of them was."""
    unread: dict[str, list[Notification]] = {}
    for n in latest:
        if n.read_at is None and n.kind in GROUPS:
            unread.setdefault(n.kind, []).append(n)
    lines, placed = [], set()
    for n in latest:
        many = unread.get(n.kind) if n.read_at is None else None
        if many and len(many) > 1:
            if n.kind not in placed:
                text, link = GROUPS[n.kind]
                lines.append(notification_out(n) | {"id": f"group:{n.kind}", "ids": [m.id for m in many], "text": text.format(n=len(many)), "link": link})
                placed.add(n.kind)
            continue
        lines.append(notification_out(n))
    return lines


@router.get("/notifications")
def my_notifications(user: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    """This person's latest notifications, newest first, several unread of a kind as
    one line, and how many need them (the bell's red number: news isn't counted)."""
    from app.routers.ledger import remind_backup

    remind_backup(db, user, settings)
    latest = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc(), Notification.id).limit(SHOWN)).all()
    return {"unread": unread_count(db, user.id), "items": grouped(latest)}


class ReadIn(Api):
    # Leave out to mark them all.
    ids: list[str] | None = Field(None, max_length=200)


@router.post("/notifications/read")
def read_notifications(user: CurrentUser, db: DB, settings: SettingsDep, body: ReadIn) -> dict:
    """Marks some (or all) of this person's notifications as read. Someone else's are never touched."""
    which = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if body.ids is not None:
        which = which.where(Notification.id.in_(body.ids))
    db.execute(which.values(read_at=utcnow()).execution_options(synchronize_session=False))
    db.commit()
    return my_notifications(user, db, settings)
