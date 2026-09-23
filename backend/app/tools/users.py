"""Sales' accounts, from the command line. Most of this is also in
Administration → Users; this is for the first account, and for scripts.

    uv run python -m app.tools.users add --email ana@example.com --name "Ana Reyes" --admin
    uv run python -m app.tools.users add --email ben@example.com --name "Ben Cruz" --role "Sales Rep" --team B2C
    uv run python -m app.tools.users list
    uv run python -m app.tools.users demo        # the demo accounts, roles and teams (development)
    uv run python -m app.tools.users password --email ana@example.com
    uv run python -m app.tools.users disable --email ana@example.com
    uv run python -m app.tools.users enable --email ana@example.com

Passwords are asked for, never passed on the command line (it would sit in
the shell's history). For scripts, set ORBIT_NEW_PASSWORD instead.
"""

import argparse
import getpass
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.demo import DEMO_ACCOUNTS, DEMO_PASSWORD
from app.migrate import upgrade
from app.models import Role, Team, User
from app.permissions import ADMINISTRATOR
from app.security import check_password_rules, hash_password

TOOL = "users tool"  # how the audit log names changes made from here


def ask_password() -> str:
    password = os.environ.get("ORBIT_NEW_PASSWORD")
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
            user.role_id, user.team_id = role.id, team.id if team else None
            audit(db, TOOL, "user.updated", target=user.email, target_type="user", target_id=user.id, fields=["roleId", "teamId"])
            updated += 1
    db.commit()
    print(f"Demo accounts: {made} made, {updated} given their role and team, {len(DEMO_ACCOUNTS) - made - updated} already set. Password: {DEMO_PASSWORD}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Sales' accounts.")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="make an account")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--admin", action="store_true", help=f"give them the {ADMINISTRATOR} role")
    add.add_argument("--role", help="the role's name (default: Sales Rep)")
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
            role = role_named(db, ADMINISTRATOR if args.admin else (args.role or "Sales Rep"))
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
