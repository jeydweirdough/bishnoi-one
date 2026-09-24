"""Insights: how each person is doing, for whoever leads them.

- A Team Lead sees the people in their team (and themselves): what each has
  done lately and what each still has to do.
- The Administrator sees everyone, and how the CRM is being used: who signs in,
  who logs their work.

Needs reports.view, within the role's reach: a team scope reaches its team,
the all scope everyone. A Salesperson, who reaches only their own records,
has their own Home instead.
"""

from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.access import Access, require
from app.api import iso, team_out
from app.deps import DB, SettingsDep
from app.models import PLANNED_KINDS, Activity, Company, Quote, SignInSession
from app.scope import reachable_people

router = APIRouter(prefix="/insights", tags=["insights"])

Reports = Annotated[Access, Depends(require("reports.view"))]


@router.get("/people")
def people_insights(access: Reports, db: DB, settings: SettingsDep) -> dict:
    if access.scope == "own":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role sees only your own work.")
    people = reachable_people(db, access)
    ids = [p.id for p in people]
    zone = ZoneInfo(settings.org_timezone)
    now = datetime.now(UTC)
    today = datetime.now(zone).date()
    start_today = datetime.combine(today, time(), zone).astimezone(UTC)
    end_today = start_today + timedelta(days=1)
    week = now - timedelta(days=7)
    month_start = datetime.combine(today.replace(day=1), time(), zone).astimezone(UTC)

    def by_owner(query) -> dict[str, int]:
        return dict(db.execute(query.group_by(Activity.owner_id)).all())

    base = select(Activity.owner_id, func.count()).where(Activity.owner_id.in_(ids))
    open_ = Activity.done_at.is_(None)
    overdue = by_owner(base.where(open_, Activity.kind.in_(PLANNED_KINDS), Activity.at < now))
    due_today = by_owner(base.where(open_, Activity.kind.in_(PLANNED_KINDS), Activity.at >= start_today, Activity.at < end_today))
    upcoming = by_owner(base.where(open_, Activity.kind.in_(PLANNED_KINDS), Activity.at >= end_today))
    done_week = by_owner(base.where(Activity.done_at >= week))
    last_done = dict(db.execute(select(Activity.owner_id, func.max(Activity.done_at)).where(Activity.owner_id.in_(ids)).group_by(Activity.owner_id)).all())
    # What kinds of work each did this week: calls, meetings, emails...
    kinds: dict[str, dict[str, int]] = defaultdict(dict)
    for owner, kind, n in db.execute(
        select(Activity.owner_id, Activity.kind, func.count()).where(Activity.owner_id.in_(ids), Activity.done_at >= week).group_by(Activity.owner_id, Activity.kind)
    ):
        kinds[owner][kind] = n
    customers = dict(db.execute(select(Company.owner_id, func.count()).where(Company.owner_id.in_(ids)).group_by(Company.owner_id)).all())
    new_customers = dict(
        db.execute(select(Company.owner_id, func.count()).where(Company.owner_id.in_(ids), Company.created_at >= month_start).group_by(Company.owner_id)).all()
    )
    quotes = {
        owner: (n, total or 0)
        for owner, n, total in db.execute(
            select(Quote.owner_id, func.count(), func.sum(Quote.total_centavos))
            .where(Quote.owner_id.in_(ids), Quote.created_at >= month_start, Quote.approval_status != "rejected", Quote.letter_status != "rejected")
            .group_by(Quote.owner_id)
        )
    }
    waiting = dict(
        db.execute(
            select(Quote.owner_id, func.count())
            .where(Quote.owner_id.in_(ids), (Quote.approval_status == "pending") | (Quote.letter_status == "pending"))
            .group_by(Quote.owner_id)
        ).all()
    )
    rejected = dict(
        db.execute(
            select(Quote.owner_id, func.count())
            .where(Quote.owner_id.in_(ids), Quote.created_at >= month_start, (Quote.approval_status == "rejected") | (Quote.letter_status == "rejected"))
            .group_by(Quote.owner_id)
        ).all()
    )
    last_sign_in = dict(db.execute(select(SignInSession.user_id, func.max(SignInSession.created_at)).where(SignInSession.user_id.in_(ids)).group_by(SignInSession.user_id)).all())
    sign_ins_week = dict(
        db.execute(select(SignInSession.user_id, func.count()).where(SignInSession.user_id.in_(ids), SignInSession.created_at >= week).group_by(SignInSession.user_id)).all()
    )

    rows = []
    for p in people:
        n, value = quotes.get(p.id, (0, 0))
        rows.append(
            {
                "id": p.id,
                "name": p.full_name,
                "role": p.role.name,
                "team": team_out(p.team),
                "isMe": p.id == access.user_id,
                "overdue": overdue.get(p.id, 0),
                "dueToday": due_today.get(p.id, 0),
                "upcoming": upcoming.get(p.id, 0),
                "doneThisWeek": done_week.get(p.id, 0),
                "doneByKind": kinds.get(p.id, {}),
                "lastActivityAt": iso(last_done.get(p.id)),
                "customers": customers.get(p.id, 0),
                "newCustomersThisMonth": new_customers.get(p.id, 0),
                "quotesThisMonth": n,
                "quotedThisMonthCentavos": int(value),
                "quotesWaiting": waiting.get(p.id, 0),
                "quotesRejectedThisMonth": rejected.get(p.id, 0),
                "lastSignInAt": iso(last_sign_in.get(p.id)),
                "signInsThisWeek": sign_ins_week.get(p.id, 0),
            }
        )
    # The ones who need a hand first: most overdue, then the quietest.
    rows.sort(key=lambda r: (not r["isMe"], -r["overdue"], r["doneThisWeek"], r["name"]))

    def total(key: str) -> int:
        return sum(r[key] for r in rows)

    return {
        "asOf": today.isoformat(),
        "monthStart": today.replace(day=1).isoformat(),
        "people": rows,
        "totals": {
            "people": len(rows),
            "signedInThisWeek": sum(1 for r in rows if r["signInsThisWeek"]),
            "activeThisWeek": sum(1 for r in rows if r["doneThisWeek"]),
            "overdue": total("overdue"),
            "dueToday": total("dueToday"),
            "doneThisWeek": total("doneThisWeek"),
            "customers": total("customers"),
            "newCustomersThisMonth": total("newCustomersThisMonth"),
            "quotesThisMonth": total("quotesThisMonth"),
            "quotedThisMonthCentavos": total("quotedThisMonthCentavos"),
            "quotesWaiting": total("quotesWaiting"),
        },
    }

