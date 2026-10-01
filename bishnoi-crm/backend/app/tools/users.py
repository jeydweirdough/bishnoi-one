"""The CRM's accounts, from the command line. Most of this is also in
Administration → Users; this is for the first account, and for scripts.

    uv run python -m app.tools.users add --email ana@example.com --name "Ana Reyes" --admin
    uv run python -m app.tools.users add --email ben@example.com --name "Ben Cruz" --role "Salesperson" --team B2C
    uv run python -m app.tools.users list
    uv run python -m app.tools.users demo        # the demo accounts, roles and teams (development)
    uv run python -m app.tools.users password --email ana@example.com
    uv run python -m app.tools.users disable --email ana@example.com
    uv run python -m app.tools.users enable --email ana@example.com

Passwords are asked for, never passed on the command line (it would sit in
the shell's history). For scripts, set BISHNOI_NEW_PASSWORD instead.
"""

import argparse
import getpass
import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.demo import (
    DEMO_ACCOUNTS,
    DEMO_ACTIVITIES,
    DEMO_BUNDLES,
    DEMO_COMPANIES,
    DEMO_CONTACTS,
    DEMO_DIVISIONS,
    DEMO_ISSUERS,
    DEMO_PASSWORD,
    RENAMED_TEAMS,
    DEMO_PRICE_TYPES,
    DEMO_PRODUCTS,
    DEMO_PROMOS,
)
from app.migrate import upgrade
from app.models import PLANNED_KINDS, Activity, Bundle, Quote, Company, Contact, Issuer, PriceType, Product, ProductPrice, Promo, Role, Team, User
from app.permissions import ADMINISTRATOR
from app.security import check_password_rules, hash_password

TOOL = "users tool"  # how the audit log names changes made from here


def ask_password() -> str:
    password = os.environ.get("BISHNOI_NEW_PASSWORD")
    if password is None:
        password = getpass.getpass("Password: ")
        if getpass.getpass("Again: ") != password:
            sys.exit("The passwords don't match.")
    problem = check_password_rules(password)
    if problem:
        sys.exit(problem)
    return password


def role_named(db: Session, name: str) -> Role:
    role = db.scalar(select(Role).where(func.lower(Role.name) == name.lower()))
    if role is None:
        names = ", ".join(db.scalars(select(Role.name).order_by(Role.name)))
        sys.exit(f"No role called {name!r}. There are: {names}.")
    return role


def team_named(db: Session, name: str, *, make: bool = False) -> Team:
    team = db.scalar(select(Team).where(func.lower(Team.name) == name.lower()))
    if team is None and make:
        team = Team(name=name)
        db.add(team)
        db.flush()
        audit(db, TOOL, "team.created", target=team.name, target_type="team", target_id=team.id)
    if team is None:
        names = ", ".join(db.scalars(select(Team.name).order_by(Team.name))) or "none yet"
        sys.exit(f"No team called {name!r}. There are: {names}.")
    return team


def make_demo(db: Session) -> None:
    if get_settings().is_production:
        sys.exit("Demo accounts are for development only.")
    made = updated = 0
    for old, new in RENAMED_TEAMS.items():
        team = db.scalar(select(Team).where(func.lower(Team.name) == old.lower()))
        if team is not None and db.scalar(select(Team).where(func.lower(Team.name) == new.lower())) is None:
            team.name = new
            audit(db, TOOL, "team.updated", target=new, target_type="team", target_id=team.id, fields=["name"])
    db.flush()
    for d in DEMO_ACCOUNTS:
        role = role_named(db, d.access)
        team = team_named(db, d.team, make=True) if d.team else None
        user = db.scalar(select(User).where(func.lower(User.email) == d.email))
        if user is None:
            user = User(email=d.email, full_name=d.name, password_hash=hash_password(DEMO_PASSWORD), role_id=role.id, team_id=team.id if team else None)
            db.add(user)
            db.flush()
            audit(db, TOOL, "user.created", target=user.email, target_type="user", target_id=user.id)
            made += 1
        elif (user.role_id, user.team_id) != (role.id, team.id if team else None):
            # A demo account that predates roles and teams gets its own.
            moved = user.team_id != (team.id if team else None)
            user.role_id, user.team_id = role.id, team.id if team else None
            audit(db, TOOL, "user.updated", target=user.email, target_type="user", target_id=user.id, fields=["roleId", "teamId"])
            if moved:
                # Demo data only: a demo rep's records go with them to their new team.
                for model in (Company, Contact, Activity, Quote):
                    db.execute(update(model).where(model.owner_id == user.id).values(team_id=user.team_id))
            updated += 1
    db.commit()
    print(f"Demo accounts: {made} made, {updated} given their role and team, {len(DEMO_ACCOUNTS) - made - updated} already set. Password: {DEMO_PASSWORD}")
    make_demo_records(db)
    make_demo_catalogue(db)
    divide_demo_catalogue(db)


def demo_divisions(db: Session, key: str) -> list[str]:
    """The ids of a demo promo's or bundle's divisions. Where none of them
    exist (a database with other teams), every team there."""
    teams = {t.name: t.id for t in db.scalars(select(Team))}
    named = [teams[n] for n in DEMO_DIVISIONS.get(key, ()) if n in teams]
    return named or list(teams.values())


def divide_demo_catalogue(db: Session) -> None:
    """Gives demo promos and bundles made before divisions (migration 0018)
    their divisions. Only ones that have none, so nothing chosen is undone."""
    changed = 0
    for promo in db.scalars(select(Promo).where(Promo.name.in_([name for name, *_ in DEMO_PROMOS]))):
        if not promo.team_ids:
            promo.team_ids = demo_divisions(db, promo.name)
            changed += 1
    for bundle in db.scalars(select(Bundle).where(Bundle.code.in_([code for code, *_ in DEMO_BUNDLES]))):
        if not bundle.team_ids:
            bundle.team_ids = demo_divisions(db, bundle.code)
            changed += 1
    if changed:
        audit(db, TOOL, "demo.catalogue_divided", target=f"{changed} promos and bundles given their divisions")
        db.commit()
        print(f"Demo promos and bundles: {changed} given their divisions.")


def make_demo_catalogue(db: Session) -> None:
    """Price types, issuers, products with prices, promos and bundles. Only
    into a database with no products yet."""
    if db.scalar(select(func.count()).select_from(Product)):
        print("Demo catalogue: skipped, there are products already.")
        return
    for n, (code, name, entry, rule, notes, approval) in enumerate(DEMO_PRICE_TYPES):
        if db.get(PriceType, code) is None:
            db.add(PriceType(code=code, name=name, entry=entry, rule=rule, requires_notes=notes, needs_approval=approval, sort_order=n))
    for code, name in DEMO_ISSUERS:
        if db.get(Issuer, code) is None:
            db.add(Issuer(code=code, name=name))
    db.flush()
    listed = [t[0] for t in DEMO_PRICE_TYPES if t[2] == "list"]
    products: dict[str, Product] = {}
    for code, name, generic, strength, form, unit, pesos in DEMO_PRODUCTS:
        products[code] = Product(
            code=code, name=name, generic_name=generic, strength=strength or None, form=form, unit=unit,
            prices=[ProductPrice(price_type_code=t, amount_centavos=p * 100) for t, p in zip(listed, pesos, strict=True)],
        )
    db.add_all(products.values())
    db.flush()
    for name, kind, terms, codes in DEMO_PROMOS:
        db.add(Promo(name=name, kind=kind, product_ids=[products[c].id for c in codes] if codes else None, team_ids=demo_divisions(db, name), **terms))
    for code, name, pesos, one_line, items in DEMO_BUNDLES:
        db.add(Bundle(
            code=code, name=name, price_centavos=pesos * 100, as_one_line=one_line,
            items=[{"productId": products[c].id, "qty": q} for c, q in items], team_ids=demo_divisions(db, code),
        ))
    summary = f"{len(DEMO_PRICE_TYPES)} price types, {len(products)} products, {len(DEMO_PROMOS)} promos, {len(DEMO_BUNDLES)} bundles"
    audit(db, TOOL, "demo.catalogue_made", target=summary)
    db.commit()
    print(f"Demo catalogue: {summary}.")


def make_demo_records(db: Session) -> None:
    """Sample companies, contacts and activities, owned by the demo reps. Only
    into a database with no companies yet, so it never doubles anything up."""
    if db.scalar(select(func.count()).select_from(Company)):
        print("Demo records: skipped, there are companies already.")
        return
    people = {u.email: u for u in db.scalars(select(User))}
    companies: dict[str, Company] = {}
    for owner_email, name, status, industry, city, phone, email in DEMO_COMPANIES:
        owner = people[owner_email]
        companies[name] = Company(
            name=name, status=status, industry=industry, city=city, country="Philippines", phone=phone, email=email,
            owner_id=owner.id, team_id=owner.team_id, created_by_id=owner.id,
        )
    db.add_all(companies.values())
    db.flush()
    contacts: dict[tuple[str, str], Contact] = {}
    for company_name, first, last, title, email, phone in DEMO_CONTACTS:
        company = companies[company_name]
        contacts[(company_name, first)] = Contact(
            company_id=company.id, first_name=first, last_name=last, job_title=title, email=email, phone=phone,
            owner_id=company.owner_id, team_id=company.team_id, created_by_id=company.owner_id,
        )
    db.add_all(contacts.values())
    db.flush()
    # On the hour, a few days either side of now: some done, some overdue, some coming up.
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    for company_name, first, kind, subject, days, done in DEMO_ACTIVITIES:
        company = companies[company_name]
        at = now + timedelta(days=days, hours=1)
        db.add(
            Activity(
                kind=kind, subject=subject, company_id=company.id,
                contact_id=contacts[(company_name, first)].id if first else None,
                at=at, done_at=(at if done else None) if kind in PLANNED_KINDS else at,
                owner_id=company.owner_id, team_id=company.team_id, created_by_id=company.owner_id,
            )
        )
    summary = f"{len(companies)} companies, {len(contacts)} contacts, {len(DEMO_ACTIVITIES)} activities"
    audit(db, TOOL, "demo.records_made", target=summary)
    db.commit()
    print(f"Demo records: {summary}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the CRM's accounts.")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="make an account")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--admin", action="store_true", help=f"give them the {ADMINISTRATOR} role")
    add.add_argument("--role", help="the role's name (default: Salesperson)")
    add.add_argument("--team", help="the team's name")
    sub.add_parser("list", help="list accounts")
    sub.add_parser("demo", help="make the demo accounts, roles and teams (development only)")
    for name in ("password", "disable", "enable"):
        sub.add_parser(name).add_argument("--email", required=True)
    args = parser.parse_args()

    engine = make_engine(get_settings().database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        if args.command == "list":
            for u in db.scalars(select(User).order_by(User.email)):
                team = u.team.name if u.team else "-"
                print(f"{u.email:34} {u.full_name:22} {u.role.name:14} {team:10} {'on' if u.is_active else 'off'}")
            return 0
        if args.command == "demo":
            make_demo(db)
            return 0

        email = args.email.strip().lower()
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if args.command == "add":
            if user is not None:
                sys.exit(f"{email} already has an account.")
            role = role_named(db, ADMINISTRATOR if args.admin else (args.role or "Salesperson"))
            team = team_named(db, args.team) if args.team else None
            user = User(email=email, full_name=args.name.strip(), password_hash=hash_password(ask_password()), role_id=role.id, team_id=team.id if team else None)
            db.add(user)
            db.flush()
            audit(db, TOOL, "user.created", target=user.email, target_type="user", target_id=user.id)
            db.commit()
            print(f"Made {email} ({role.name}{f', {team.name}' if team else ''}).")
            return 0
        if user is None:
            sys.exit(f"No account for {email}.")
        if args.command == "password":
            user.password_hash = hash_password(ask_password())
            user.password_changed_at = datetime.now(UTC)  # ends every session it had
            audit(db, TOOL, "user.password_reset", target=user.email, target_type="user", target_id=user.id)
        else:
            user.is_active = args.command == "enable"
            audit(db, TOOL, "user.switched_on" if user.is_active else "user.switched_off", target=user.email, target_type="user", target_id=user.id)
        db.commit()
        print(f"{args.command}: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
