"""Splits the B2B division in two (decided 2026-10-19): B2B NBD (new business:
new customers, inactive for 2-3 months, dormant after one order and 6 months)
and B2B CRR (existing customers, retention).

    uv run python -m app.tools.split_b2b --company getmeds            # shows what it would do
    uv run python -m app.tools.split_b2b --company getmeds --apply

- "B2B" is renamed "B2B NBD": its people, customers, deals and quotes stay with it.
- "B2B CRR" is made beside it, managed by the same manager, with the same
  settings: wherever a setting names B2B in a list of teams (customer types,
  form fields and sections, promos, bundles, quote templates...), B2B CRR is
  added beside it; B2B's own price types and retention windows are copied.
- People named with --crr move to B2B CRR as their main team; the team lead
  keeps NBD as main team and gets CRR as another team (so they lead both).
- Customer types for both: Clinic is added, Drugstore is opened to them, and
  Drugstore chain and Wholesaler are retired (customers keep the type they have).
- The customer form for both: "Our products they carry" and "Credit status"
  are worked out now (app/trade.py), so the typed ones are taken off the form
  (what was typed stays); "2MG sales, last 12 months" is added, for the B2B
  profile until 2MG's own sales can be read.

Runs again safely: what's done already is left as it is.
"""

import json
import sys

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import CustomerType, FormField, FormSection, Team, TeamPriceType, User, UserTeam
from app.tenants import for_tool

TOOL = "split B2B tool"
OLD, NBD, CRR = "B2B", "B2B NBD", "B2B CRR"
# Who works on existing customers (decided 2026-10-19): Fritzi.
CRR_PEOPLE = ("sales1@2mginc.com",)
TEAM_LEAD = "sales5@2mginc.com"  # Jessa: leads both


def team_named(db: Session, name: str) -> Team | None:
    return db.scalar(select(Team).where(Team.name == name))


def lists_naming(db: Session, team_id: str) -> list[tuple[str, str, str, str, list]]:
    """Every (table, key column, key, column, list) whose value is a JSON list of team ids holding this team."""
    found = []
    insp = inspect(db.get_bind())
    for table in insp.get_table_names():
        if not table.startswith("nbcm_"):
            continue
        keys = insp.get_pk_constraint(table)["constrained_columns"]
        if len(keys) != 1:
            continue
        key = keys[0]
        for col in insp.get_columns(table):
            name = col["name"]
            if name in (key,) or str(col["type"]).upper() not in ("JSON", "TEXT", "VARCHAR") and "JSON" not in str(col["type"]).upper():
                continue
            rows = db.execute(text(f'SELECT "{key}", "{name}" FROM "{table}" WHERE CAST("{name}" AS TEXT) LIKE :p'), {"p": f"%{team_id}%"}).all()
            for row_key, raw in rows:
                try:
                    value = raw if isinstance(raw, list) else json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if isinstance(value, list) and team_id in value:
                    found.append((table, key, row_key, name, value))
    return found


def run(db: Session, apply: bool) -> None:
    old = team_named(db, OLD)
    nbd = team_named(db, NBD) or old
    if nbd is None:
        sys.exit(f"No team called {OLD!r} or {NBD!r} here.")
    plan: list[str] = []
    if nbd.name == OLD:
        plan.append(f"rename team {OLD!r} to {NBD!r}")
        if apply:
            nbd.name = NBD
            audit(db, TOOL, "team.updated", target=NBD, target_type="team", target_id=nbd.id, fields=["name"])
    crr = team_named(db, CRR)
    if crr is None:
        plan.append(f"make team {CRR!r} (manager, sharing and retention windows as {NBD})")
        if apply:
            crr = Team(name=CRR, description="Existing customers: retention.", manager_id=nbd.manager_id, share_customers=nbd.share_customers,
                       at_risk_days=nbd.at_risk_days, lost_days=nbd.lost_days, headquarters=list(nbd.headquarters or []))
            db.add(crr)
            db.flush()
            audit(db, TOOL, "team.created", target=CRR, target_type="team", target_id=crr.id)
    if apply and nbd.description is None:
        nbd.description = "New business: new customers, inactive 2-3 months, dormant after one order and 6 months."

    # B2B's settings, for CRR too.
    crr_id = crr.id if crr is not None else "<new>"
    for table, key, row_key, col, value in lists_naming(db, nbd.id):
        if crr is not None and crr.id in value:
            continue
        plan.append(f"add {CRR} beside {NBD} in {table}.{col} ({row_key})")
        if apply:
            db.execute(text(f'UPDATE "{table}" SET "{col}" = :v WHERE "{key}" = :k'), {"v": json.dumps([*value, crr_id]), "k": row_key})
    for tpt in list(db.scalars(select(TeamPriceType).where(TeamPriceType.team_id == nbd.id))):
        if crr is None or db.get(TeamPriceType, (crr.id, tpt.price_type_code)) is None:
            plan.append(f"price type {tpt.price_type_code} for {CRR}")
            if apply:
                db.add(TeamPriceType(team_id=crr_id, price_type_code=tpt.price_type_code))

    # People.
    for email in CRR_PEOPLE:
        u = db.scalar(select(User).where(User.email == email))
        if u is not None and (crr is None or u.team_id != crr.id):
            plan.append(f"move {u.full_name} to {CRR}")
            if apply:
                u.team_id = crr_id
                audit(db, TOOL, "user.updated", target=u.email, target_type="user", target_id=u.id, fields=["teamId"])
    lead = db.scalar(select(User).where(User.email == TEAM_LEAD))
    for person in [x for x in (lead, db.get(User, nbd.manager_id) if nbd.manager_id else None) if x is not None]:
        if crr is None or db.get(UserTeam, (person.id, crr.id)) is None:
            plan.append(f"{person.full_name} also in {CRR}")
            if apply:
                db.add(UserTeam(user_id=person.id, team_id=crr_id))

    # Customer types for B2B: Clinic and Drugstore for both teams; the chain and wholesaler retired.
    both = [nbd.id, crr_id]
    clinic = db.get(CustomerType, "clinic")
    if clinic is None:
        plan.append("add customer type Clinic for both teams")
        if apply:
            top = max([t.sort_order for t in db.scalars(select(CustomerType))] or [0])
            db.add(CustomerType(code="clinic", name="Clinic", color="blue", sort_order=top + 1, only_teams=both, except_teams=[]))
    drugstore = db.get(CustomerType, "drugstore")
    if drugstore is not None and not all(t in (drugstore.only_teams or []) for t in both) and drugstore.only_teams:
        plan.append("open customer type Drugstore to both teams")
        if apply:
            drugstore.only_teams = list(dict.fromkeys([*(drugstore.only_teams or []), *both]))
    for code in ("drugstore_chain", "wholesaler"):
        t = db.get(CustomerType, code)
        if t is not None and t.is_active:
            plan.append(f"retire customer type {t.name}")
            if apply:
                t.is_active = False

    # The customer form: the worked-out fields off it, the 2MG figure on it.
    for key in ("x_products_carried", "x_credit_status"):
        f = db.scalar(select(FormField).where(FormField.entity == "company", FormField.key == key))
        if f is not None and not f.hidden:
            plan.append(f"take the typed field {f.label!r} off the customer form (worked out now)")
            if apply:
                f.hidden = True
    if db.scalar(select(FormField).where(FormField.entity == "company", FormField.key == "x_2mg_sales")) is None:
        plan.append("add the field '2MG sales, last 12 months' for both teams")
        if apply:
            carried = db.scalar(select(FormField).where(FormField.entity == "company", FormField.key == "x_products_carried"))
            section = carried.section_id if carried is not None else None
            if section is None:
                s = FormSection(entity="company", title="Trade profile", columns=2, sort_order=99)
                db.add(s)
                db.flush()
                section = s.id
            db.add(FormField(entity="company", key="x_2mg_sales", label="2MG sales, last 12 months", type="money", section_id=section, sort_order=90,
                             help_text="What 2MG sold them over the last 12 months. Added to GetMeds' sales for the Priority and High priority profile.",
                             options=[], only_teams=both, except_teams=[], only_types=[], except_types=[]))

    for line in plan or ["nothing to do: already split"]:
        print(("done: " if apply else "would: ") + line)
    if apply:
        audit(db, TOOL, "b2b.split", target=f"{len(plan)} changes")
        db.commit()


def main() -> int:
    company, url = for_tool(sys.argv)
    print(f"Company: {company}")
    engine = make_engine(url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        run(db, "--apply" in sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
