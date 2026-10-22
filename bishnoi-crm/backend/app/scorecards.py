"""Scorecards: each division's monthly 100-point score from its sales playbook
(models.Scorecard), worked out from the KPIs it names.

A person's scorecard is the one for their team, or the division it's a branch
of (the nearest wins), and their role. Each item takes a KPI's result for the
month and turns it into points by its bands:

- on "attainment": the result against the person's target (or a fixed number,
  "of": 80 doctors), as a percentage; on "value": the result as it is (a rate,
  days of DSO, a score entered by hand);
- scope "own": the person's own result; "team": their team's (a coach's
  district, a mentor's division: the team and its branches), against the
  team's target or its people's added up; "team_average": the average of
  their people's attainment, 0 when anyone is under "floorEach" (TTAR, CTAR).

A missed gate caps the month ("cap": IST under 60% keeps the total at 40; a
group's "groupCap": the gatekeeper set under 40 keeps it at 70). The total, as
a share of what the card is out of, falls in one of its performance bands,
with the yearly raise and whether a PIP follows.

A result that can't be had (no target, Finance not linked) scores nothing and
says so, rather than guessing.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kpis import FROM_FINANCE, Figure, Period, combine, dso_days, figures, unit_of, value_of
from app.models import Kpi, KpiTarget, Scorecard, Team, User


@dataclass
class Context:
    db: Session
    period: Period
    people: list[User]
    teams: dict[str, Team]
    kpis: dict[str, Kpi]
    _figures: dict[str, dict[str, Figure]] = field(default_factory=dict)
    _targets: dict | None = None

    def figures(self, kpi: Kpi) -> dict[str, Figure]:
        if kpi.code not in self._figures:
            self._figures[kpi.code] = figures(self.db, kpi, [p.id for p in self.people], self.period)
        return self._figures[kpi.code]

    def target(self, kpi: Kpi, user_id: str | None = None, team_id: str | None = None) -> int | None:
        if self._targets is None:
            rows = self.db.scalars(select(KpiTarget).where(KpiTarget.month == self.period.month))
            self._targets = {(t.kpi_id, t.user_id or t.team_id): t.value for t in rows}
        return self._targets.get((kpi.id, user_id or team_id))

    def members(self, person: User) -> list[User]:
        """A coach's or mentor's people: everyone in their team and its branches."""
        if not person.team_id:
            return []
        inside = {person.team_id} | {t.id for t in self.teams.values() if t.parent_id == person.team_id}
        return [p for p in self.people if p.team_id in inside]


def chain(person: User, teams: dict[str, Team]) -> list[str]:
    """The person's team, then the division it's a branch of."""
    out, tid = [], person.team_id
    while tid and tid not in out:
        out.append(tid)
        tid = teams[tid].parent_id if tid in teams else None
    return out


def card_of(person: User, cards: list[Scorecard], teams: dict[str, Team]) -> Scorecard | None:
    """The scorecard for the person's role at their nearest team that has one."""
    mine = [c for c in cards if not c.roles or person.role_id in c.roles]
    for tid in chain(person, teams):
        for c in mine:
            if tid in (c.teams or []):
                return c
    return next((c for c in mine if not c.teams), None)


def points_for(bands: list[dict], x: float) -> float:
    """The first band that fits ("min": at least, "max": at most, neither: anything)."""
    for b in bands:
        if ("min" not in b or x >= b["min"]) and ("max" not in b or x <= b["max"]):
            return b["points"]
    return 0


def attainment(actual: int | None, target: int | None) -> float | None:
    if actual is None or not target:
        return None
    return round(100 * actual / target, 1)


def result(item: dict, kpi: Kpi, person: User, ctx: Context) -> dict:
    """The item's figure for the person: {actual, target, x} (x is what the bands read)."""
    unit, got, scope = unit_of(kpi), ctx.figures(kpi), item.get("scope", "own")
    if kpi.measure in FROM_FINANCE and ctx.period.sales() is None:
        return {"actual": None, "target": None, "x": None}
    if scope == "team_average":
        rates = []
        for m in ctx.members(person):
            if m.id == person.id:
                continue
            rate = attainment(value_of(got.get(m.id), unit), ctx.target(kpi, user_id=m.id))
            if rate is not None:
                rates.append(rate)
        if not rates:
            return {"actual": None, "target": None, "x": None}
        if item.get("floorEach") is not None and min(rates) < item["floorEach"]:
            return {"actual": round(sum(rates) / len(rates), 1), "target": None, "x": 0}
        avg = round(sum(rates) / len(rates), 1)
        return {"actual": avg, "target": None, "x": avg}
    if scope == "team":
        members = ctx.members(person)
        parts = [got[m.id] for m in members if m.id in got]
        if kpi.measure == "dso":
            # Days don't add up: the team's DSO is what all its customers owe over all its sales.
            actual = dso_days(ctx.period, [m.id for m in members])
        else:
            actual = combine(parts, unit) if parts or unit != "percent" else None
        own = ctx.target(kpi, team_id=person.team_id) if person.team_id else None
        summed = [t for t in (ctx.target(kpi, user_id=m.id) for m in members) if t is not None]
        target = own if own is not None else (sum(summed) if summed and unit != "percent" else None)
    else:
        actual = value_of(got.get(person.id), unit)
        target = ctx.target(kpi, user_id=person.id)
    if item.get("on") == "attainment":
        target = item.get("of") or target
        return {"actual": actual, "target": target, "x": attainment(actual, target)}
    return {"actual": actual, "target": target, "x": actual}


def score(card: Scorecard, person: User, ctx: Context) -> dict:
    """The person's month on their scorecard: each item's points, the total, caps and band."""
    rows, total, out_of, caps, groups = [], 0.0, 0.0, [], {}
    for item in card.items or []:
        out_of += item["points"]
        kpi = ctx.kpis.get(item["kpi"])
        if kpi is None:
            rows.append({"kpi": item["kpi"], "name": item.get("label") or item["kpi"], "points": 0, "of": item["points"], "missing": "This KPI isn't set up."})
            continue
        r = result(item, kpi, person, ctx)
        pts = points_for(item.get("bands") or [], r["x"]) if r["x"] is not None else 0
        missing = None
        if r["x"] is None:
            missing = "No target set." if item.get("on") == "attainment" and r["actual"] is not None else "No result yet."
        cap = item.get("cap")
        if cap and r["x"] is not None and r["x"] < cap["below"]:
            caps.append({"total": cap["total"], "why": f"{item.get('label') or kpi.name} under {cap['below']}"})
        if item.get("group"):
            g = groups.setdefault(item["group"], {"points": 0.0, "cap": None})
            g["points"] += pts
            g["cap"] = item.get("groupCap") or g["cap"]
        total += pts
        rows.append({
            "kpi": kpi.code, "name": item.get("label") or kpi.name, "unit": unit_of(kpi), "on": item.get("on", "value"),
            "scope": item.get("scope", "own"), "actual": r["actual"], "target": r["target"], "x": r["x"],
            "points": pts, "of": item["points"], "group": item.get("group"), "missing": missing,
        })
    for name, g in groups.items():
        if g["cap"] and g["points"] < g["cap"]["below"]:
            caps.append({"total": g["cap"]["total"], "why": f"{name.capitalize()} set under {g['cap']['below']}"})
    cap = min(caps, key=lambda c: c["total"]) if caps else None
    if cap and total > cap["total"]:
        total = cap["total"]
    # Nothing to score yet (no results, no targets): no score, rather than a 0 that reads as a PIP.
    scored = any(r.get("x") is not None for r in rows)
    percent = round(100 * total / out_of, 1) if out_of and scored else None
    band = next((b for b in card.bands or [] if percent is not None and percent >= b["min"]), None)
    return {"items": rows, "total": round(total, 1), "outOf": out_of, "percent": percent, "cap": cap, "band": band}
