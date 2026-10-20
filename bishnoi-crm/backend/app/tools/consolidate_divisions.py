"""Lays the CRM's divisions out as the 2026 org chart and the sales structure
workbook agree (decided 2026-10-19):

- HOS (Vanessa): branches TeleSales, the field areas (NCR 1, NCR 2, North and
  Central Luzon, South Luzon, Visayas, Mindanao), Government Account and
  Patient Assistance Program. Each area's district coach leads it (role
  District coach: a field agent who sees their branch); Vanessa leads Visayas.
- Prescription Business (Javed): branches STC, URO and B&B; the territory
  leads (Sheila, Mitzi, Khalygen, Benjie) and Honey are in all three.
- B2C (Javed): branch MD Telesales (the chart's Oncology MD Telesales).
- B2B (Subir): branches B2B NBD and B2B CRR. Government Bidding (BID) and
  CLIDP stay divisions of their own under Subir.
- Modern Trade (Malou) as it is; 2MG SCM (supply chain, not sales) switched off.

A branch gets its division's manager. A branch with no settings of its own
(a new field area, MD Telesales) gets every setting its division has (customer
types, form fields, promos, bundles, price types...); one that already has its
own (TeleSales, STC, URO, B&B, NBD, CRR) keeps them as they are. Someone who
moves to another team takes their records with them (records keep the team
they were given under). New people are added with placeholder emails
(neededtochange1@getmeds.ph ...) and no usable password until those are set.

    uv run python -m app.tools.consolidate_divisions --company getmeds            # shows what it would do
    uv run python -m app.tools.consolidate_divisions --company getmeds --apply

Runs again safely: what's done already is left as it is.
"""

import json
import secrets
import sys

from sqlalchemy import inspect, select, text, update
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Base, Owned, Role, RolePermission, Team, TeamPriceType, User, UserTeam
from app.security import hash_password
from app.tenants import for_tool

TOOL = "consolidate divisions tool"
DISTRICT_COACH = "District coach"

# Division: (manager's name, description). Created when missing.
DIVISIONS = {
    "HOS": ("Vanessa Tolentino Escalderon", "Hospital Division"),
    "Prescription Business": ("Javed Shaikh", "Prescription Business (Onco-Hema): STC, URO and B&B"),
    "B2C": ("Javed Shaikh", "B2C Sales Coaching: MD Telesales (oncology)"),
    "B2B": ("Subir Dey", "B2B Telesales: new business (NBD) and client retention and reorder (CRR)"),
}
# Branch: (division, description, lead's name or None). Created when missing.
BRANCHES = {
    "TeleSales": ("HOS", "MD Telesales: Anesthesia", None),
    "Field NCR 1": ("HOS", "Hospital field sales: NCR 1", "Daniel Andrew Pacificador Cruz"),
    "Field NCR 2": ("HOS", "Hospital field sales: NCR 2", "Jim Lord Baron Dacpano Palomares"),
    "Field North and Central Luzon": ("HOS", "Hospital field sales: North and Central Luzon", "Julius Santos Abucay"),
    "Field South Luzon": ("HOS", "Hospital field sales: South Luzon", "Kindred Gadil Malaluan"),
    "Field Visayas": ("HOS", "Hospital field sales: Visayas (led by the business mentor)", None),
    "Field Mindanao": ("HOS", "Hospital field sales: Mindanao", "Saurav Kumar"),
    "Government Account": ("HOS", "Hospital Division: government accounts", None),
    "Patient Assistance Program": ("HOS", "Hospital Division: patient assistance program", None),
    "STC": ("Prescription Business", None, None),
    "URO": ("Prescription Business", None, None),
    "B&B": ("Prescription Business", None, None),
    "MD Telesales": ("B2C", "Oncology MD Telesales", None),
    "B2B NBD": ("B2B", None, None),
    "B2B CRR": ("B2B", None, None),
}
# Main team of each person, by full name as the CRM has it.
MAIN_TEAM = {
    "Field NCR 1": ["Daniel Andrew Pacificador Cruz", "Ryan Noel Panganiban Aninon", "Luis Jasper Eduarte Palingping", "Ana Mae De Miguel Otucan", "Patrick Labrador Adion"],
    "Field NCR 2": ["Jim Lord Baron Dacpano Palomares", "Ma. Princess Muena Cuerdo", "Jacob Canturna Cruz", "Den Jane Regalado Suarez", "Jomari Esguerra"],
    "Field North and Central Luzon": ["Julius Santos Abucay", "Paolo Estangco Paradero", "Gabrielle Shannen Bermudez Agripa", "Nicole Anne Cue Castillo"],
    "Field South Luzon": ["Kindred Gadil Malaluan", "Clarisse Lodana Deocareza", "Lalien Jean Madrona Nunez", "John Michael Aragon Orig", "John Glenn Ramirez Bernabe"],
    "Field Visayas": ["Andrea Lyn Nasayao Bermido", "Kristofferson Dela Pena Conde", "Jessa Mae Montialbucio Teruel"],
    "Field Mindanao": ["Saurav Kumar", "Melanie Zuello Diaz", "Rubelyn Bautista Ramos", "Welmar Moralla Pancho", "Harley Queen Verano Orani", "Maycarl Degamo"],
    "Government Account": ["Reynan Cuenca"],
    "Patient Assistance Program": ["Fhaye Norella"],
    "MD Telesales": ["Honey Salve Cordero", "Cesar Geronimo Gutierez", "Mary Jane Marquez Vinas", "Emmanuel Greg Escalona"],
    "STC": ["Mitzi Villa Francisco", "Benjie Dan Lacebal"],
    "B2B": ["Subir Dey"],
    "B2B NBD": ["Winbelle Faith Gomez", "Pillow", "KC"],
    "BID": ["Aljean Carno"],
}
# Also in these teams (leads over several branches).
OTHER_TEAMS = {
    "Honey Salve Cordero": ["STC", "URO", "B&B"],
    "Sheila Mae Yape Bazar": ["STC", "URO"],
    "Mitzi Villa Francisco": ["URO", "B&B"],
    "Khalygen Lopez Boayes": ["STC", "URO"],
    "Benjie Dan Lacebal": ["URO", "B&B"],
    "Subir Dey": ["B2B NBD", "B2B CRR", "BID", "CLIDP"],
    "Vanessa Tolentino Escalderon": ["Field Visayas"],
}
# Role changes.
ROLES = {
    "Daniel Andrew Pacificador Cruz": DISTRICT_COACH,
    "Jim Lord Baron Dacpano Palomares": DISTRICT_COACH,
    "Julius Santos Abucay": DISTRICT_COACH,
    "Kindred Gadil Malaluan": DISTRICT_COACH,
    "Saurav Kumar": DISTRICT_COACH,
    "Claire Yu Gallana": "Team Lead",  # B2B district sales coach, Mindanao
    "Kate Labaclado Cagoyong": "Salesperson",  # not the Davao/Cebu lead ("KZ" is Benjie)
}
# New people: name, role. Emails neededtochange1@getmeds.ph and on, in this order.
NEW_PEOPLE = [
    ("KC", "Salesperson"),
    ("Pillow", "Salesperson"),
    ("Winbelle Faith Gomez", "Salesperson"),
    ("Benjie Dan Lacebal", "Team Lead"),
    ("Emmanuel Greg Escalona", "Salesperson"),
    ("Jomari Esguerra", "Field agent"),
    ("Maycarl Degamo", "Field agent"),
    ("Reynan Cuenca", "Salesperson"),
    ("Fhaye Norella", "Salesperson"),
    ("Aljean Carno", "Salesperson"),
]
# Out of sales: no team (on the chart in IT).
NO_TEAM = ["Linus Aurin"]
SWITCH_OFF = ["2MG SCM"]
DESCRIBE = {"BID": "Government Bidding", "CLIDP": "CLIDP Institutional", "Modern Trade": "Modern Trade / Drugstore Channel"}


class Plan:
    def __init__(self, apply: bool):
        self.apply, self.lines = apply, []

    def say(self, line: str) -> bool:
        self.lines.append(line)
        return self.apply


def owned_models():
    return [m.class_ for m in Base.registry.mappers if issubclass(m.class_, Owned)]


def lists_naming(db: Session, team_id: str):
    """Every (table, key column, key, column, list) whose JSON list of team ids holds this team."""
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
            if name == key or "JSON" not in str(col["type"]).upper():
                continue
            for row_key, raw in db.execute(text(f'SELECT "{key}", "{name}" FROM "{table}" WHERE CAST("{name}" AS TEXT) LIKE :p'), {"p": f"%{team_id}%"}).all():
                try:
                    value = raw if isinstance(raw, list) else json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if isinstance(value, list) and team_id in value:
                    found.append((table, key, row_key, name, value))
    return found


def run(db: Session, apply: bool) -> list[str]:
    plan = Plan(apply)
    people = {u.full_name: u for u in db.scalars(select(User))}
    teams = {t.name: t for t in db.scalars(select(Team))}
    roles = {r.name: r for r in db.scalars(select(Role))}

    # The District coach role: a field agent's permissions, reaching their branch.
    if DISTRICT_COACH not in roles:
        field = roles["Field agent"]
        if plan.say(f"make role {DISTRICT_COACH!r} (Field agent's permissions, scope: their team)"):
            coach = Role(name=DISTRICT_COACH, description="Leads a field area: visits doctors, and sees the whole branch's records.", scope="team",
                         grants=[RolePermission(permission=p) for p in field.permissions])
            db.add(coach)
            db.flush()
            roles[DISTRICT_COACH] = coach

    # New people, with placeholder emails.
    taken = {u.email for u in people.values()}
    n = 1
    for name, role in NEW_PEOPLE:
        if name in people:
            continue
        while f"neededtochange{n}@getmeds.ph" in taken:
            n += 1
        email = f"neededtochange{n}@getmeds.ph"
        taken.add(email)
        if plan.say(f"add {name} ({role}) as {email}"):
            u = User(email=email, full_name=name, password_hash=hash_password(secrets.token_urlsafe(32)), role_id=roles[role].id)
            db.add(u)
            db.flush()
            audit(db, TOOL, "user.created", target=email, target_type="user", target_id=u.id)
            people[name] = u

    # Divisions, then branches.
    for name, (manager, about) in DIVISIONS.items():
        m = people.get(manager)
        t = teams.get(name)
        if t is None:
            if plan.say(f"make division {name!r} (manager {manager})"):
                t = Team(name=name, description=about, manager_id=m.id if m else None)
                db.add(t)
                db.flush()
                audit(db, TOOL, "team.created", target=name, target_type="team", target_id=t.id)
                teams[name] = t
        elif t.parent_id is not None or (m and t.manager_id != m.id) or (about and t.description != about):
            if plan.say(f"set division {name!r}: manager {manager}, description"):
                t.parent_id, t.description = None, about or t.description
                if m:
                    t.manager_id = m.id
    for name, (division, about, _lead) in BRANCHES.items():
        d = teams.get(division)
        t = teams.get(name)
        d_id = d.id if d else f"<{division}>"
        if t is None:
            if plan.say(f"make branch {division} · {name}"):
                t = Team(name=name, description=about, parent_id=d.id, manager_id=d.manager_id, share_customers=d.share_customers)
                db.add(t)
                db.flush()
                audit(db, TOOL, "team.created", target=name, target_type="team", target_id=t.id)
                teams[name] = t
        elif t.parent_id != d_id or (d and t.manager_id != d.manager_id) or (about and t.description != about):
            if plan.say(f"put {name!r} under {division} (its manager, description)"):
                t.parent_id = d.id
                t.manager_id = d.manager_id
                if about:
                    t.description = about
                audit(db, TOOL, "team.updated", target=name, target_type="team", target_id=t.id, fields=["parentId", "managerId"])
    for name, about in DESCRIBE.items():
        t = teams.get(name)
        if t is not None and t.description != about and plan.say(f"describe {name!r} as {about!r}"):
            t.description = about
    for name in SWITCH_OFF:
        t = teams.get(name)
        if t is not None and t.is_active and plan.say(f"switch off {name!r} (not a sales division)"):
            t.is_active = False

    # A branch with no settings of its own takes its division's.
    for name, (division, _a, _l) in BRANCHES.items():
        d, t = teams.get(division), teams.get(name)
        if d is None or t is None:
            continue
        if lists_naming(db, t.id) or db.scalar(select(TeamPriceType).where(TeamPriceType.team_id == t.id)) is not None:
            continue  # it has settings of its own: kept as they are
        for table, key, row_key, col, value in lists_naming(db, d.id):
            if t.id not in value and plan.say(f"{name}: {division}'s setting in {table}.{col}"):
                db.execute(text(f'UPDATE "{table}" SET "{col}" = :v WHERE "{key}" = :k'), {"v": json.dumps([*value, t.id]), "k": row_key})
        for tpt in list(db.scalars(select(TeamPriceType).where(TeamPriceType.team_id == d.id))):
            if db.get(TeamPriceType, (t.id, tpt.price_type_code)) is None and plan.say(f"{name}: price type {tpt.price_type_code}"):
                db.add(TeamPriceType(team_id=t.id, price_type_code=tpt.price_type_code))

    # People: main team (records go with them), roles, other teams, out of sales.
    def move(u: User, team: Team | None) -> None:
        u.team_id = team.id if team else None
        for model in owned_models():
            db.execute(update(model).where(model.owner_id == u.id).values(team_id=u.team_id))
        audit(db, TOOL, "user.updated", target=u.email, target_type="user", target_id=u.id, fields=["teamId"])

    for team_name, names in MAIN_TEAM.items():
        t = teams.get(team_name)
        for name in names:
            u = people.get(name)
            if u is None:
                plan.lines.append(f"!! {name} not found")
                continue
            if t is None or u.team_id != t.id:
                if plan.say(f"{name} → {team_name} (and their records)"):
                    move(u, t)
    for name, role in ROLES.items():
        u = people.get(name)
        if u is not None and u.role.name != role and plan.say(f"{name}: role {u.role.name} → {role}"):
            u.role_id = roles[role].id
            audit(db, TOOL, "user.updated", target=u.email, target_type="user", target_id=u.id, fields=["roleId"])
    for name, team_names in OTHER_TEAMS.items():
        u = people.get(name)
        for team_name in team_names:
            t = teams.get(team_name)
            if u is None:
                continue
            if t is None or (t.id != u.team_id and db.get(UserTeam, (u.id, t.id)) is None):
                if plan.say(f"{name} also in {team_name}"):
                    db.add(UserTeam(user_id=u.id, team_id=t.id))
    for name in NO_TEAM:
        u = people.get(name)
        if u is not None and u.team_id is not None and plan.say(f"{name}: out of sales (no team)"):
            move(u, None)

    if apply:
        audit(db, TOOL, "divisions.consolidated", target=f"{len(plan.lines)} changes")
        db.commit()
    return plan.lines


def main() -> int:
    company, url = for_tool(sys.argv)
    print(f"Company: {company}")
    engine = make_engine(url)
    upgrade(engine)
    apply = "--apply" in sys.argv
    with make_sessions(engine)() as db:
        lines = run(db, apply)
    for line in lines or ["nothing to do: already laid out"]:
        print(("done: " if apply else "would: ") + line if not line.startswith("!!") else line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
