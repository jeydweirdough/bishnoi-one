"""KPI management.

- /kpis: the KPIs, and the measures a KPI can count (for the screens).
- /admin/kpis: defining them (admin.settings). Built-in ones (with a code) keep
  what they measure; they can be renamed, retuned or hidden, not deleted.
- /kpi-targets: each KPI's target for a month, per person and per team
  (goals.manage). A team with no target of its own has its people's added up.
- /kpi-entries: results of manual KPIs, entered by hand (goals.manage).
- /kpi-scorecard: results against targets, one's own, or (goals.view or
  reports.view, with a scope wider than own) everyone one's role reaches.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated, Literal
from app.pricing import sales_settings
from app.terms import terms_of

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import Access, CurrentAccess, require
from app.api import Api, camel, changed, field_error, not_found, person_out, team_out
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app.kpis import FILTER_CHOICES, MEASURES, UNITS, Period, combine, elapsed_in, figures, judged, unit_of, value_of
from app.models import KPI_BETTER, Activity, Company, Kpi, KpiEntry, KpiTarget, Product, Quote, Role, Team, User, Visit
from app.pricing import today
from app.routers.field import month_bounds, month_or_now, this_month
from app.scope import reachable_people

router = APIRouter(tags=["kpis"])

Configure = Annotated[Access, Depends(require("admin.settings"))]
SetGoals = Annotated[Access, Depends(require("goals.manage"))]


def period_of(month: str, settings: Settings) -> Period:
    start, end = month_bounds(month, settings)
    y, m = int(month[:4]), int(month[5:])
    after = date(y + m // 12, m % 12 + 1, 1)
    return Period(month=month, start=start, end=end, first_day=f"{month}-01", next_first_day=after.isoformat())


def worded(db: Session, text: str) -> str:
    """A measure's words in the company's own: "Accounts visited" is "Doctors visited" at GetMeds."""
    many = terms_of(sales_settings(db).terms)["visited"]["many"]
    return text.replace("Accounts", many).replace("accounts", many.lower())


def kpi_out(db: Session, k: Kpi, roles: dict[str, str]) -> dict:
    measure = MEASURES.get(k.measure)
    flt = next(iter((k.filters or {}).items()), None)
    if flt and flt[0] == "productId":
        product = db.get(Product, flt[1])
        flt_label = product.name if product else "A product no longer listed"
    elif flt:
        flt_label = str(flt[1]).replace("_", " ").capitalize()
    else:
        flt_label = None
    return {
        "id": k.id,
        "code": k.code,
        "name": k.name,
        "description": k.description,
        "measure": k.measure,
        "measureLabel": worded(db, measure.label) if measure else "Entered by hand",
        "filters": k.filters or {},
        "filterLabel": flt_label,
        "unit": unit_of(k),
        "better": k.better,
        "roles": [{"id": r, "name": roles[r]} for r in k.roles or [] if r in roles],
        "greenAt": k.green_at,
        "amberAt": k.amber_at,
        "isActive": k.is_active,
        "builtIn": k.code is not None,
        "sortOrder": k.sort_order,
    }


def all_kpis(db: Session, *, active_only: bool) -> list[Kpi]:
    q = select(Kpi).order_by(Kpi.sort_order, func.lower(Kpi.name))
    return list(db.scalars(q.where(Kpi.is_active) if active_only else q))


def role_names(db: Session) -> dict[str, str]:
    return {r.id: r.name for r in db.scalars(select(Role))}


def applies(k: Kpi, person: User) -> bool:
    return not k.roles or person.role_id in k.roles


@router.get("/kpis")
def list_kpis(me: CurrentUser, access: CurrentAccess, db: DB, everything: bool = Query(False, alias="all")) -> dict:
    """The KPIs (switched-off ones too, with `all`, for Settings), and what a KPI can measure."""
    if everything:
        access.require("admin.settings")
    roles = role_names(db)
    return {
        "items": [kpi_out(db, k, roles) for k in all_kpis(db, active_only=not everything)],
        "measures": [{"key": key, "label": worded(db, m.label), "unit": m.unit, "about": worded(db, m.about), "filter": m.filter} for key, m in MEASURES.items()],
        "filterChoices": {key: list(values) for key, values in FILTER_CHOICES.items()},
        "roles": [{"id": i, "name": n} for i, n in sorted(roles.items(), key=lambda r: r[1].lower())],
    }


# --- defining them -----------------------------------------------------------------------------


class KpiFields(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    measure: str | None = Field(None, max_length=40)
    filters: dict[str, str] | None = None
    unit: Literal["count", "money", "percent"] | None = None
    better: Literal["higher", "lower"] | None = None
    roles: list[str] | None = Field(None, max_length=50)
    green_at: int | None = Field(None, ge=1, le=1000)
    amber_at: int | None = Field(None, ge=0, le=1000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class KpiIn(KpiFields):
    name: str = Field(min_length=1, max_length=80)
    measure: str = Field(max_length=40)


def check_kpi(db: Session, k: Kpi) -> None:
    """The whole KPI, as it would be saved."""
    if k.measure != "manual" and k.measure not in MEASURES:
        raise field_error("measure", "Pick what it measures from the list.")
    takes = MEASURES[k.measure].filter if k.measure in MEASURES else None
    filters = {key: v for key, v in (k.filters or {}).items() if v}
    if any(key != takes for key in filters):
        raise field_error("filters", "This measure can't be narrowed that way.")
    for key, value in filters.items():
        if key in FILTER_CHOICES and value not in FILTER_CHOICES[key]:
            raise field_error("filters", "Pick one from the list.")
        if key == "productId" and db.get(Product, value) is None:
            raise field_error("filters", "Pick a product from the list.")
    k.filters = filters
    if k.unit not in UNITS:
        raise field_error("unit", "Pick count, amount or percentage.")
    if k.better not in KPI_BETTER:
        raise field_error("better", "Say whether higher or lower is better.")
    if k.amber_at > k.green_at:
        raise field_error("amberAt", "\"Slightly behind\" has to start below \"On target\".")
    known = set(role_names(db))
    if any(r not in known for r in k.roles or []):
        raise field_error("roles", "Pick roles from the list.")
    taken = db.scalar(select(Kpi).where(func.lower(Kpi.name) == k.name.lower(), Kpi.id != k.id))
    if taken is not None:
        raise field_error("name", "Another measure already has this name.")


@router.post("/admin/kpis", status_code=status.HTTP_201_CREATED)
def create_kpi(access: Configure, me: CurrentUser, db: DB, body: KpiIn) -> dict:
    last = db.scalar(select(func.max(Kpi.sort_order))) or 0
    k = Kpi(
        name=body.name,
        description=(body.description or "").strip() or None,
        measure=body.measure,
        filters=body.filters or {},
        unit=body.unit or "count",
        better=body.better or "higher",
        roles=body.roles or [],
        green_at=body.green_at or 100,
        amber_at=body.amber_at if body.amber_at is not None else 80,
        is_active=True if body.is_active is None else body.is_active,
        sort_order=last + 1,
    )
    check_kpi(db, k)
    db.add(k)
    db.flush()
    audit(db, me, "kpi.created", target=k.name, target_type="kpi", target_id=k.id)
    db.commit()
    return kpi_out(db, k, role_names(db))


@router.patch("/admin/kpis/{kpi_id}")
def update_kpi(access: Configure, me: CurrentUser, db: DB, kpi_id: str, body: KpiFields) -> dict:
    k = db.get(Kpi, kpi_id)
    if k is None:
        raise not_found("measure")
    wanted = changed(body)
    if k.code and ({"measure", "filters"} & set(wanted)) and (wanted.get("measure", k.measure) != k.measure or (wanted.get("filters") or {}) != (k.filters or {})):
        raise HTTPException(status.HTTP_409_CONFLICT, "A built-in measure keeps what it measures. Add a new measure for something else.")
    if "name" in wanted and not wanted["name"]:
        raise field_error("name", "Give the measure a name.")
    if "description" in wanted:
        wanted["description"] = (wanted["description"] or "").strip() or None
    fields = []
    for key, value in wanted.items():
        if value is None and key not in ("description",):
            continue
        if getattr(k, key) != value:
            setattr(k, key, value)
            fields.append(key)
    check_kpi(db, k)
    if fields:
        audit(db, me, "kpi.updated", target=k.name, target_type="kpi", target_id=k.id, fields=camel(fields))
        db.commit()
    return kpi_out(db, k, role_names(db))


@router.delete("/admin/kpis/{kpi_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kpi(access: Configure, me: CurrentUser, db: DB, kpi_id: str) -> Response:
    """A KPI and its targets and results go. A built-in one is switched off instead."""
    k = db.get(Kpi, kpi_id)
    if k is None:
        raise not_found("measure")
    if k.code:
        raise HTTPException(status.HTTP_409_CONFLICT, "A built-in measure can't be deleted. Switch it off instead.")
    audit(db, me, "kpi.deleted", target=k.name, target_type="kpi", target_id=k.id)
    db.delete(k)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class OrderIn(Api):
    ids: list[str] = Field(max_length=200)


@router.put("/admin/kpis/order")
def order_kpis(access: Configure, me: CurrentUser, db: DB, body: OrderIn) -> dict:
    kpis = {k.id: k for k in db.scalars(select(Kpi))}
    for n, i in enumerate(body.ids):
        if i in kpis:
            kpis[i].sort_order = n
    audit(db, me, "kpi.reordered", target="KPIs", target_type="kpi")
    db.commit()
    return list_kpis(me, access, db, everything=True)


# --- targets and hand-entered results ---------------------------------------------------------------


def people_for(db: Session, kpis: list[Kpi], month: str, extra: set[str] = frozenset()) -> list[User]:
    """Everyone a KPI applies to (and anyone with a target or result that month already)."""
    return [
        u
        for u in db.scalars(select(User).where(User.is_active).order_by(func.lower(User.full_name)))
        if not u.role.is_system and any(applies(k, u) for k in kpis) or u.id in extra
    ]


# Whose targets: everyone's for a role that reaches every record, else the
# people and teams of the departments they reach (access.runs).
@router.get("/kpi-targets")
def read_targets(access: SetGoals, me: CurrentUser, db: DB, settings: SettingsDep, month: str | None = Query(None, max_length=7)) -> dict:
    month = month_or_now(month, settings)
    kpis = all_kpis(db, active_only=True)
    ids = [k.id for k in kpis]
    targets = list(db.scalars(select(KpiTarget).where(KpiTarget.month == month, KpiTarget.kpi_id.in_(ids))))
    entries = list(db.scalars(select(KpiEntry).where(KpiEntry.month == month, KpiEntry.kpi_id.in_(ids))))
    people = [p for p in people_for(db, kpis, month, {t.user_id for t in targets if t.user_id}) if access.runs(p.team_id)]
    per_person: dict[str, dict] = {}
    per_team: dict[str, dict] = {}
    for t in targets:
        (per_person.setdefault(t.user_id, {}) if t.user_id else per_team.setdefault(t.team_id, {}))[t.kpi_id] = t.value
    entered: dict[str, dict] = {}
    for e in entries:
        entered.setdefault(e.user_id, {})[e.kpi_id] = e.value
    roles = role_names(db)
    return {
        "month": month,
        "kpis": [kpi_out(db, k, roles) for k in kpis],
        "people": [
            {
                "person": person_out(p),
                "team": team_out(p.team),
                "role": p.role.name,
                "roleId": p.role_id,
                "applies": [k.id for k in kpis if applies(k, p)],
                "targets": per_person.get(p.id, {}),
                "entries": entered.get(p.id, {}),
            }
            for p in people
        ],
        "teams": [{"team": team_out(t), "targets": per_team.get(t.id, {})} for t in db.scalars(select(Team).order_by(func.lower(Team.name))) if access.runs(t.id)],
    }


class TargetIn(Api):
    kpi_id: str = Field(max_length=36)
    user_id: str | None = Field(None, max_length=36)
    team_id: str | None = Field(None, max_length=36)
    # None takes the target away.
    value: int | None = Field(None, ge=0, le=10**13)


class TargetsIn(Api):
    targets: list[TargetIn] = Field(max_length=5000)


@router.put("/kpi-targets")
def set_targets(access: SetGoals, me: CurrentUser, db: DB, settings: SettingsDep, body: TargetsIn, month: str | None = Query(None, max_length=7)) -> dict:
    month = month_or_now(month, settings)
    kpis = {k.id: k for k in db.scalars(select(Kpi))}
    users = {u.id for u in db.scalars(select(User)) if access.runs(u.team_id)}
    teams = {t for t in db.scalars(select(Team.id)) if access.runs(t)}
    for n, t in enumerate(body.targets):
        if t.kpi_id not in kpis:
            raise field_error(f"targets.{n}.kpiId", "Pick a KPI from the list.")
        if (t.user_id is None) == (t.team_id is None):
            raise field_error(f"targets.{n}", "A target is for one person or one team.")
        if (t.user_id and t.user_id not in users) or (t.team_id and t.team_id not in teams):
            raise field_error(f"targets.{n}", "No such person or team.")
        if t.value is not None and unit_of(kpis[t.kpi_id]) == "percent" and t.value > 100:
            raise field_error(f"targets.{n}.value", "A percentage is at most 100.")
        whose = KpiTarget.user_id == t.user_id if t.user_id else KpiTarget.team_id == t.team_id
        found = db.scalar(select(KpiTarget).where(KpiTarget.kpi_id == t.kpi_id, KpiTarget.month == month, whose))
        if t.value is None:
            if found is not None:
                db.delete(found)
            continue
        found = found or KpiTarget(kpi_id=t.kpi_id, month=month, user_id=t.user_id, team_id=t.team_id)
        found.value = t.value
        db.add(found)
    audit(db, me, "kpi_targets.updated", target=f"KPI targets for {month} ({len(body.targets)})", target_type="goals")
    db.commit()
    return read_targets(access, me, db, settings, month)


class EntryIn(Api):
    kpi_id: str = Field(max_length=36)
    user_id: str = Field(max_length=36)
    value: int | None = Field(None, ge=0, le=10**13)
    note: str | None = Field(None, max_length=200)


class EntriesIn(Api):
    entries: list[EntryIn] = Field(max_length=5000)


@router.put("/kpi-entries")
def set_entries(access: SetGoals, me: CurrentUser, db: DB, settings: SettingsDep, body: EntriesIn, month: str | None = Query(None, max_length=7)) -> dict:
    """Results of KPIs entered by hand. None takes one away."""
    month = month_or_now(month, settings)
    for n, e in enumerate(body.entries):
        k = db.get(Kpi, e.kpi_id)
        if k is None or k.measure != "manual":
            raise field_error(f"entries.{n}.kpiId", "Only a KPI entered by hand takes results here.")
        person = db.get(User, e.user_id)
        if person is None or not access.runs(person.team_id):
            raise field_error(f"entries.{n}.userId", "No such person.")
        found = db.scalar(select(KpiEntry).where(KpiEntry.kpi_id == k.id, KpiEntry.month == month, KpiEntry.user_id == e.user_id))
        if e.value is None:
            if found is not None:
                db.delete(found)
            continue
        found = found or KpiEntry(kpi_id=k.id, month=month, user_id=e.user_id)
        found.value, found.note, found.entered_by_id = e.value, (e.note or "").strip() or None, me.id
        db.add(found)
    audit(db, me, "kpi_entries.updated", target=f"KPI results for {month} ({len(body.entries)})", target_type="goals")
    db.commit()
    return read_targets(access, me, db, settings, month)


# --- the scorecard ------------------------------------------------------------------------------


@router.get("/kpi-scorecard")
def scorecard(
    access: CurrentAccess,
    me: CurrentUser,
    db: DB,
    settings: SettingsDep,
    month: str | None = Query(None, max_length=7),
    view: Literal["mine", "team"] = "mine",
    team: str | None = Query(None, max_length=36),
    role: str | None = Query(None, max_length=36, description="the team view shows one role at a time: its people, and the KPIs that are for it"),
) -> dict:
    month = month_or_now(month, settings)
    if view == "team":
        if not (access.can("goals.view") or access.can("reports.view")):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role sees only your own results.")
        if access.scope == "own":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role sees only your own work.")
    period = period_of(month, settings)
    elapsed = elapsed_in(period, today(settings.org_timezone))
    kpis = all_kpis(db, active_only=True)
    if view == "mine":
        people = [me]
    else:
        everyone = [u for u in reachable_people(db, access) if (not team or u.team_id == team) and not u.role.is_system and any(applies(k, u) for k in kpis)]
        # One role at a time: a salesperson's KPIs and a field agent's aren't the same, so they aren't one table.
        counts: dict[str, int] = {}
        for u in everyone:
            counts[u.role_id] = counts.get(u.role_id, 0) + 1
        names = {u.role_id: u.role.name for u in everyone}
        roles = sorted(counts, key=lambda r: (-counts[r], names[r].lower()))
        role = role if role in counts else (roles[0] if roles else None)
        people = [u for u in everyone if u.role_id == role]
        kpis = [k for k in kpis if not k.roles or role in k.roles]
        role_tabs = [{"id": r, "name": names[r], "people": counts[r]} for r in roles]
    ids = [p.id for p in people]
    targets = list(db.scalars(select(KpiTarget).where(KpiTarget.month == month, KpiTarget.kpi_id.in_([k.id for k in kpis]))))
    person_target = {(t.kpi_id, t.user_id): t.value for t in targets if t.user_id}
    team_target = {(t.kpi_id, t.team_id): t.value for t in targets if t.team_id}

    results: dict[str, dict[str, dict]] = {p.id: {} for p in people}
    teams: dict[str | None, dict[str, dict]] = {}
    totals: dict[str, dict] = {}
    for k in kpis:
        unit = unit_of(k)
        got = figures(db, k, ids, period)
        whose = [p for p in people if applies(k, p)]
        for p in whose:
            actual = value_of(got.get(p.id), unit)
            target = person_target.get((k.id, p.id))
            results[p.id][k.id] = {"actual": actual, "target": target, **judged(k, actual, target, elapsed)}
        # Teams: their people's results combined; their own target, else their people's added up.
        by_team: dict[str | None, list[User]] = {}
        for p in whose:
            by_team.setdefault(p.team_id, []).append(p)
        for tid, members in by_team.items():
            actual = combine([got[p.id] for p in members if p.id in got], unit) if unit == "percent" else sum(results[p.id][k.id]["actual"] or 0 for p in members)
            # A team's own target covers everyone the KPI is for: in one role's
            # view it stands only when the KPI is for that role alone.
            own = team_target.get((k.id, tid)) if tid and (view == "mine" or (k.roles or []) == [role]) else None
            summed = [person_target[(k.id, p.id)] for p in members if (k.id, p.id) in person_target]
            target = own if own is not None else (sum(summed) if summed and unit != "percent" else None)
            teams.setdefault(tid, {})[k.id] = {"actual": actual, "target": target, "ownTarget": own is not None, **judged(k, actual, target, elapsed)}
        if view == "team" and whose:
            actual = combine([got[p.id] for p in whose if p.id in got], unit) if unit == "percent" else sum(results[p.id][k.id]["actual"] or 0 for p in whose)
            team_sums = [v["target"] for v in (teams[t].get(k.id) for t in teams) if v and v["target"] is not None]
            target = sum(team_sums) if team_sums and unit != "percent" else None
            totals[k.id] = {"actual": actual, "target": target, **judged(k, actual, target, elapsed)}

    roles = role_names(db)
    team_rows = {t.id: t for t in db.scalars(select(Team))}
    return {
        "month": month,
        "thisMonth": this_month(settings),
        "elapsed": round(elapsed, 3),
        "view": view,
        "kpis": [kpi_out(db, k, roles) for k in kpis],
        "people": [{"person": person_out(p), "team": team_out(p.team), "results": results[p.id]} for p in sorted(people, key=lambda u: u.full_name.lower())],
        "teams": [
            {"team": team_out(team_rows.get(tid)) if tid else None, "results": r}
            for tid, r in sorted(teams.items(), key=lambda kv: (team_rows[kv[0]].name.lower() if kv[0] in team_rows else "~"))
        ] if view == "team" else [],
        "totals": totals,
        "roles": role_tabs if view == "team" else [],
        "role": role if view == "team" else None,
        "canSetTargets": access.can("goals.manage"),
    }


@router.get("/playbook-scorecard")
def playbook_scorecard(
    access: CurrentAccess,
    me: CurrentUser,
    db: DB,
    settings: SettingsDep,
    month: str | None = Query(None, max_length=7),
    team: str | None = Query(None, max_length=36),
) -> dict:
    """100-Point Composite Scorecard aligned with Bishnoi Sales Playbooks.

    Weights:
    - IST (Individual Sales Target): 40 pts. Hard floor: <60% attainment = 0 pts + mandatory PIP!
    - DSO / Collections Efficiency: 20 pts (>=95%: 20, 85-94%: 15, 75-84%: 10, <75%: 0).
    - CRR / HRR Retention Rate: 20 pts (>=90%: 20, 80-89%: 15, 70-79%: 10, <70%: 0).
    - NZSD (Net Zero-Sales Days): 20 pts (<=3 days: 20, 4-5 days: 15, 6-8 days: 10, >8 days: 0).

    Performance Bands:
    - 95-100: Distinguished (+10% to +15% annual merit increment)
    - 85-94: High Performer (+6% to +8% increment)
    - 70-84: Core Performer (+3% to +5% increment)
    - 60-69: PIP Candidate (0% increment, 30-day coaching)
    - <60: Critical Action (0% increment, immediate PIP/escalation)
    """
    month = month_or_now(month, settings)
    period = period_of(month, settings)
    now_day = today(settings.org_timezone)
    elapsed = elapsed_in(period, now_day)

    # Determine people in scope
    if access.scope == "own":
        people = [me]
    else:
        people = [
            u for u in reachable_people(db, access)
            if (not team or u.team_id == team) and not u.role.is_system
        ]

    ids = [p.id for p in people]

    # Target values for revenue_won and amount_collected
    rev_kpi = db.scalar(select(Kpi).where(Kpi.code == "revenue_won"))
    col_kpi = db.scalar(select(Kpi).where(Kpi.code == "amount_collected"))

    rev_targets: dict[str, int] = {}
    col_targets: dict[str, int] = {}
    if rev_kpi:
        for t in db.scalars(select(KpiTarget).where(KpiTarget.month == month, KpiTarget.kpi_id == rev_kpi.id, KpiTarget.user_id.in_(ids))):
            if t.user_id:
                rev_targets[t.user_id] = t.value
    if col_kpi:
        for t in db.scalars(select(KpiTarget).where(KpiTarget.month == month, KpiTarget.kpi_id == col_kpi.id, KpiTarget.user_id.in_(ids))):
            if t.user_id:
                col_targets[t.user_id] = t.value

    # Actual figures
    rev_actuals = MEASURES["deals_won_value"].count(db, ids, period, {}) if "deals_won_value" in MEASURES else {}
    col_actuals = MEASURES["collections_amount"].count(db, ids, period, {}) if "collections_amount" in MEASURES else {}

    # Activity days for NZSD (days where rep logged a visit or created a quote)
    activity_days_by_user: dict[str, set[str]] = defaultdict(set)
    for owner_id, v_at in db.execute(select(Visit.owner_id, Visit.visited_at).where(Visit.owner_id.in_(ids), Visit.visited_at >= period.start, Visit.visited_at < period.end)):
        if v_at:
            activity_days_by_user[owner_id].add(v_at.date().isoformat())
    for owner_id, q_at in db.execute(select(Quote.owner_id, Quote.created_at).where(Quote.owner_id.in_(ids), Quote.created_at >= period.start, Quote.created_at < period.end)):
        if q_at:
            activity_days_by_user[owner_id].add(q_at.date().isoformat())

    # Elapsed days in the month so far
    start_d = date.fromisoformat(period.first_day)
    end_d = min(date.fromisoformat(now_day), date.fromisoformat(period.next_first_day) - timedelta(days=1))
    elapsed_days = max(1, (end_d - start_d).days + 1)
    # Approximate business days (weekdays)
    biz_days = sum(1 for i in range(elapsed_days) if (start_d + timedelta(days=i)).weekday() < 5)

    scorecards = []
    for p in people:
        # 1. IST Quota Achievement (40 pts)
        ist_target = rev_targets.get(p.id) or 0
        ist_actual = rev_actuals.get(p.id, (0, None))[0]
        if ist_target > 0:
            ist_attainment = round((ist_actual / ist_target) * 100, 1)
        else:
            ist_attainment = 100.0 if ist_actual > 0 else 0.0

        if ist_target > 0 and ist_attainment < 60.0:
            ist_pts = 0.0
            hard_floor_penalty = True
        else:
            ist_pts = round(min(40.0, (ist_attainment / 100.0) * 40.0), 1)
            hard_floor_penalty = False

        # 2. DSO / Collections Efficiency (20 pts)
        col_target = col_targets.get(p.id) or 0
        col_actual = col_actuals.get(p.id, (0, None))[0]
        if col_target > 0:
            col_attainment = round((col_actual / col_target) * 100, 1)
            if col_attainment >= 95.0:
                dso_pts = 20.0
            elif col_attainment >= 85.0:
                dso_pts = 15.0
            elif col_attainment >= 75.0:
                dso_pts = 10.0
            else:
                dso_pts = 0.0
        else:
            col_attainment = 100.0 if col_actual > 0 else None
            dso_pts = 20.0 if col_actual > 0 else 15.0

        # 3. CRR / Retention Rate (20 pts)
        total_accounts = db.scalar(select(func.count(Company.id)).where(Company.owner_id == p.id, Company.status != "inactive")) or 0
        visited_accounts = len({
            cid for cid, in db.execute(
                select(Visit.company_id).where(Visit.owner_id == p.id, Visit.visited_at >= period.start, Visit.visited_at < period.end, Visit.company_id.isnot(None))
            )
        })
        if total_accounts > 0:
            retention_rate = round(min(100.0, (visited_accounts / total_accounts) * 100), 1)
        else:
            retention_rate = 95.0 if visited_accounts > 0 else 85.0

        if retention_rate >= 90.0:
            crr_pts = 20.0
        elif retention_rate >= 80.0:
            crr_pts = 15.0
        elif retention_rate >= 70.0:
            crr_pts = 10.0
        else:
            crr_pts = 0.0

        # 4. NZSD (Net Zero-Sales Days) (20 pts)
        active_days_count = len(activity_days_by_user.get(p.id, set()))
        zero_days = max(0, biz_days - active_days_count)
        if zero_days <= 3:
            nzsd_pts = 20.0
        elif zero_days <= 5:
            nzsd_pts = 15.0
        elif zero_days <= 8:
            nzsd_pts = 10.0
        else:
            nzsd_pts = 0.0

        # Total Composite Score
        total_score = round(ist_pts + dso_pts + crr_pts + nzsd_pts, 1)

        # Performance Band & Governance
        if hard_floor_penalty or total_score < 60.0:
            band = "Critical Action"
            status_tag = "critical"
            pip_required = True
            merit_increment = "0%"
            action_plan = "Immediate 30-Day PIP or Escalation to Division Head"
        elif total_score < 70.0:
            band = "PIP Candidate"
            status_tag = "warning"
            pip_required = True
            merit_increment = "0%"
            action_plan = "Structured 30-Day PIP & Weekly One-on-One Coaching"
        elif total_score < 85.0:
            band = "Core Performer"
            status_tag = "good"
            pip_required = False
            merit_increment = "+3% to +5%"
            action_plan = "Standard Coaching & Target Alignment"
        elif total_score < 95.0:
            band = "High Performer"
            status_tag = "good"
            pip_required = False
            merit_increment = "+6% to +8%"
            action_plan = "Leadership Track & Key Account Expansion"
        else:
            band = "Distinguished"
            status_tag = "excellent"
            pip_required = False
            merit_increment = "+10% to +15%"
            action_plan = "President's Club & Strategic Mentorship"

        scorecards.append({
            "person": person_out(p),
            "team": team_out(p.team),
            "role": p.role.name,
            "totalScore": total_score,
            "band": band,
            "status": status_tag,
            "pipRequired": pip_required,
            "hardFloorPenalty": hard_floor_penalty,
            "meritIncrement": merit_increment,
            "actionPlan": action_plan,
            "breakdown": {
                "ist": {
                    "points": ist_pts,
                    "maxPoints": 40.0,
                    "targetCentavos": ist_target,
                    "actualCentavos": ist_actual,
                    "attainmentPct": ist_attainment,
                    "floorPenalty": hard_floor_penalty,
                },
                "dso": {
                    "points": dso_pts,
                    "maxPoints": 20.0,
                    "targetCentavos": col_target,
                    "actualCentavos": col_actual,
                    "attainmentPct": col_attainment,
                },
                "crr": {
                    "points": crr_pts,
                    "maxPoints": 20.0,
                    "retentionRatePct": retention_rate,
                    "visitedAccounts": visited_accounts,
                    "totalAccounts": total_accounts,
                },
                "nzsd": {
                    "points": nzsd_pts,
                    "maxPoints": 20.0,
                    "zeroDays": zero_days,
                    "activeDays": active_days_count,
                    "businessDays": biz_days,
                },
            },
        })

    avg_score = round(sum(s["totalScore"] for s in scorecards) / len(scorecards), 1) if scorecards else 0.0
    pip_count = sum(1 for s in scorecards if s["pipRequired"])

    return {
        "month": month,
        "elapsed": round(elapsed, 3),
        "totalPeople": len(scorecards),
        "averageScore": avg_score,
        "pipCount": pip_count,
        "scorecards": scorecards,
    }
