"""Home: each person's dashboard, built from what their access lets them do.

- mine: my goals in each sales division I sell in, and my retention trend;
- teams: with Reports in one division, the team's goals and a row per person;
- divisions: with Reports in more than one, a row per division instead;
- finance / inventory / admin: each department's queue and goals, for whoever works there.

Targets come from Settings -> Goals (app/goals.py, /admin/goals below).
"""

import calendar
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access import Access, access_for_everyone, is_on
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentAccess, CurrentUser, RecordsDep, SettingsDep, require_settings
from app.errors import invalid
from app.goals import AREA_DIVISION, BY_KEY as GOALS, Month, SalesMonth, catalog_out, goal_divisions, goal_results
from app.goals import load_targets, measure_sales, set_tracked, tracked
from app.models import Division, GoalTarget, Membership, PriceType, Product, Profile, Promo
from app.catalogue import sales_keys
from app.modules import BY_KEY, REPORT
from app.price_book import load_rules as load_price_rules
from app.quotes import QUOTE
from app.retention import load_rules, look_back, trend
from app.routers.retention import counts_as_buying, find_all, gather, iso_at_start, local_day
from app.routers.sales import ACTIVITY, FOLLOW_UP, today_date
from app.schemas import GoalTargetsIn
from app.scope import Scope
from app.store.query import Cmp, Eq, In
from app.store.records import Records
from app.tenancy import org_get


router = APIRouter(tags=["home"])


def month_of(today: date) -> Month:
    return Month(today.replace(day=1), today, calendar.monthrange(today.year, today.month)[1])


def own(access: Access, module: str, action: str) -> frozenset[Scope]:
    return frozenset(s for s in access.scopes(module, action) if s.division == module)


def sales_month(records: Records, scopes: frozenset[Scope], settings: Settings, month: Month, rules) -> SalesMonth:
    start = iso_at_start(month.start, settings)
    follow_ups = find_all(
        records, FOLLOW_UP, scopes, (Cmp("dueOn", ">=", month.start.isoformat()), Cmp("dueOn", "<=", month.today.isoformat()))
    )
    return SalesMonth(
        customers=gather(records, scopes, settings, look_back(rules, month.today)),
        quotes=[q for q in find_all(records, QUOTE, scopes, (Cmp("createdAt", ">=", start),)) if counts_as_buying(q)],
        activities=find_all(records, ACTIVITY, scopes, (Cmp("occurredAt", ">=", start),)),
        follow_ups=follow_ups,
        done_on={f["_id"]: local_day(f["doneAt"], settings).isoformat() for f in follow_ups if f.get("doneAt")},
    )


def roster(everyone: dict, module: str, scopes: frozenset[Scope]) -> list[Profile]:
    """The team: everyone who can add records in these scopes (reps, leads, heads), not read-only viewers."""
    people = [p for p, a in everyone.values() if any(a.can_in(module, "create", s) for s in scopes)]
    return sorted(people, key=lambda p: p.full_name.casefold())


def average_days(docs: list[dict], field: str) -> float | None:
    spans = [
        (datetime.fromisoformat(d[field].replace("Z", "+00:00")) - datetime.fromisoformat(d["createdAt"].replace("Z", "+00:00"))).total_seconds() / 86400
        for d in docs
        if d.get(field) and d.get("createdAt")
    ]
    return round(sum(spans) / len(spans), 1) if spans else None


def finance_desk(
    records: Records, access: Access, settings: Settings, month: Month, targets: dict, keys: set[str], sales: tuple[str, ...]
) -> dict:
    scopes = frozenset(s for s in access.scopes("finance", "view") if s.division in sales)
    start = iso_at_start(month.start, settings)
    approvals = find_all(records, QUOTE, scopes, (Eq("approvalStatus", "pending"),))
    letters = find_all(records, QUOTE, scopes, (Eq("letterStatus", "pending"),))
    to_pay = find_all(records, QUOTE, scopes, (Eq("letterStatus", "verified"), In("paymentStatus", ("unpaid", "partial"))))
    waiting: dict[str, tuple[dict, str]] = {d["_id"]: (d, "approval") for d in approvals}
    for d in letters:
        waiting.setdefault(d["_id"], (d, "letter"))
    oldest = sorted(waiting.values(), key=lambda x: x[0]["createdAt"])[:5]
    values = {
        "approval_days": average_days(find_all(records, QUOTE, scopes, (Cmp("approvalAt", ">=", start),)), "approvalAt"),
        "letter_days": average_days(find_all(records, QUOTE, scopes, (Cmp("letterAt", ">=", start),)), "letterAt"),
    }
    return {
        "counts": {"approvals": len(approvals), "letters": len(letters), "payments": len(to_pay)},
        "unpaidCentavos": sum(d["letter"]["amountCentavos"] - d.get("paidCentavos", 0) for d in to_pay),
        "oldest": [
            {
                "id": d["_id"],
                "number": d["number"],
                "customerName": d.get("customerName"),
                "divisionName": BY_KEY[d["division"]].name,
                "task": task,
                "ageDays": (month.today - local_day(d["createdAt"], settings)).days,
                "totalCentavos": d["totalCentavos"],
            }
            for d, task in oldest
        ],
        "goals": goal_results(values, targets["finance"], month, goals=(GOALS["approval_days"], GOALS["letter_days"]), keys=keys),
    }


def inventory_desk(db: Session, month: Month, targets: dict, keys: set[str]) -> dict:
    types = db.scalars(select(PriceType).where(PriceType.entry == "list", PriceType.is_active.is_(True))).all()
    products = db.scalars(select(Product).where(Product.is_active.is_(True)).options(selectinload(Product.prices)).order_by(Product.name)).all()
    missing = []
    for p in products:
        have = {x.price_type_code for x in p.prices}
        gaps = [t.name for t in types if t.code not in have]
        if gaps:
            missing.append({"id": p.id, "name": p.name, "code": p.code, "missing": gaps})
    week = month.today + timedelta(days=7)
    promos = db.scalars(select(Promo).where(Promo.is_active.is_(True))).all()
    promo = lambda p, on: {"id": p.id, "name": p.name, "on": on.isoformat()}  # noqa: E731
    fully = round((len(products) - len(missing)) / len(products) * 10_000) if products else None
    return {
        "products": len(products),
        "missingCount": len(missing),
        "missing": missing[:5],
        "starting": [promo(p, p.starts_on) for p in promos if month.today < p.starts_on <= week],
        "ending": [promo(p, p.ends_on) for p in promos if p.ends_on and month.today <= p.ends_on <= week],
        "goals": goal_results({"fully_priced": fully}, targets["inventory"], month, goals=(GOALS["fully_priced"],), keys=keys),
    }


def admin_desk(db: Session) -> dict:
    rows = db.execute(
        select(Profile, Membership).join(Membership, Membership.user_id == Profile.id).options(selectinload(Profile.assignments))
    ).all()
    on = [p for p, m in rows if is_on(p, m)]
    no_role = sorted((p for p in on if not p.assignments), key=lambda p: p.full_name.casefold())
    return {
        "people": len(on),
        "switchedOff": len(rows) - len(on),
        "noRoleCount": len(no_role),
        "noRole": [{"id": p.id, "name": p.full_name} for p in no_role[:5]],
        # Divisions whose reps can't quote yet because no price is switched on
        # for them. A division that quotes with notes rather than a price list
        # (BID bids) is not missing anything, so it is never named here.
        "noPrices": [
            division_names(db).get(k, k)
            for k in sales_keys(db)
            if (rules := load_price_rules(db, k)).uses_price_list and not rules.price_types
        ],
    }


@router.get("/me/dashboard")
def dashboard(user: CurrentUser, access: CurrentAccess, db: DB, records: RecordsDep, settings: SettingsDep) -> dict:
    today = today_date(settings)
    month = month_of(today)
    rules = load_rules(db)
    targets = load_targets(db)
    rules_out = lambda k: {"atRiskDays": rules[k].at_risk_days, "lostDays": rules[k].lost_days}  # noqa: E731
    # What this company watches. Everything below reports only these, so a goal
    # switched off in Settings simply isn't there rather than showing as missed.
    watched = tracked(db)
    sales = sales_keys(db)
    out: dict = {
        "today": today.isoformat(),
        "month": {"start": month.start.isoformat(), "days": month.days, "day": today.day},
        "goals": catalog_out(watched),
        "mine": [],
        "teams": [],
        "divisions": [],
        "finance": None,
        "inventory": None,
        "admin": None,
    }

    # Mine: the divisions I sell in (can add records), not the ones I only look at.
    for k in sales:
        if not own(access, k, "create"):
            continue
        data = sales_month(records, own(access, k, "view"), settings, month, rules)
        mine = [c for c in data.customers if c.owner_id == user.id]
        out["mine"].append(
            {
                "division": k,
                "name": BY_KEY[k].name,
                "rules": rules_out(k),
                "customers": len(mine),
                "goals": goal_results(measure_sales(data, {user.id}, rules, month), targets[k], month, keys=watched),
                "trend": trend(mine, rules, today),
            }
        )

    # Team figures where I have Reports: per person in one division, per division across several.
    reporting = {k: s for k in sales if (s := own(access, k, REPORT))}
    everyone = access_for_everyone(db) if reporting else {}
    for k, scopes in reporting.items():
        data = sales_month(records, scopes, settings, month, rules)
        team = roster(everyone, k, scopes)
        entry = {
            "division": k,
            "name": BY_KEY[k].name,
            "rules": rules_out(k),
            "people": len(team),
            "goals": goal_results(measure_sales(data, None, rules, month), targets[k], month, reps=len(team), keys=watched),
            "trend": trend(data.customers, rules, today),
        }
        if len(reporting) == 1:
            entry["rows"] = [
                {"id": p.id, "name": p.full_name, "goals": goal_results(measure_sales(data, {p.id}, rules, month), targets[k], month, keys=watched)}
                for p in team
            ]
            out["teams"].append(entry)
        else:
            out["divisions"].append(entry)

    if access.can("finance", "view"):
        out["finance"] = finance_desk(records, access, settings, month, targets, watched, sales)
    if access.can("inventory", "view"):
        out["inventory"] = inventory_desk(db, month, targets, watched)
    if access.manage_settings:
        out["admin"] = admin_desk(db)
    return out


# --- Settings -> Goals -----------------------------------------------------------------


def division_names(db: Session) -> dict[str, str]:
    return dict(db.execute(select(Division.code, Division.name)).all())


def area_of(division: str, sales: tuple[str, ...]) -> str:
    return "sales" if division in sales else next(a for a, d in AREA_DIVISION.items() if d == division)


def targets_out(db: Session) -> dict:
    names = division_names(db)
    sales = sales_keys(db)
    return {
        "goals": catalog_out(tracked(db)),
        "divisions": [
            {"code": d, "name": names.get(d, d), "area": area_of(d, sales)} for d in goal_divisions(db) if d in names
        ],
        "targets": load_targets(db),
    }


@router.get("/admin/goals", tags=["settings"], dependencies=[Depends(require_settings)])
def goal_targets(db: DB) -> dict:
    return targets_out(db)


@router.put("/admin/goals/tracked", tags=["settings"], dependencies=[Depends(require_settings)])
def set_tracked_goals(keys: Annotated[list[str], Body(embed=True, max_length=40)], db: DB, me: CurrentUser) -> dict:
    """Which goals this company watches. Orbit can work all of them out; a
    company that doesn't care about one simply stops seeing it. Targets are
    kept either way, so switching one back on doesn't lose what it was set to."""
    unknown = [k for k in keys if k not in GOALS]
    if unknown:
        raise invalid(f"{unknown[0]} isn't a goal.")
    set_tracked(db, set(keys))
    db.commit()
    audit(db, me, "goals.tracked_changed", ", ".join(sorted(keys)) or "none")
    return targets_out(db)


@router.put("/admin/goals", tags=["settings"], dependencies=[Depends(require_settings)])
def replace_goal_targets(body: GoalTargetsIn, db: DB, me: CurrentUser) -> dict:
    sales = sales_keys(db)
    divisions = goal_divisions(db)
    names = dict(db.execute(select(Division.code, Division.name)).all())
    for division, goals in body.targets.items():
        if division not in divisions:
            raise invalid(f"{division} doesn't have goals.")
        for key, target in goals.items():
            goal = GOALS.get(key)
            if goal is None or goal.area != area_of(division, sales):
                raise invalid(f"{key} isn't one of {names.get(division, division)}'s goals.")
            if target < 0 or (goal.unit == "percent" and target > 10_000) or target > 100_000_000_000:
                raise invalid(f"{goal.name}: that target is out of range.")
    for division, goals in body.targets.items():
        for key, target in goals.items():
            row = org_get(db, GoalTarget, division, key) or GoalTarget(division_code=division, goal=key)
            row.target = target
            db.add(row)
    db.commit()
    audit(db, me, "goals.changed", ", ".join(sorted(body.targets)))
    return targets_out(db)
