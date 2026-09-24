"""Inventory's accounts, from the command line. There is no sign-up page.

    uv run python -m app.tools.users add --email ana@example.com --name "Ana Reyes" [--role Warehouse]
    uv run python -m app.tools.users list
    uv run python -m app.tools.users demo        # demo accounts and demo stock (development)
    uv run python -m app.tools.users password --email ana@example.com
    uv run python -m app.tools.users disable --email ana@example.com
    uv run python -m app.tools.users enable --email ana@example.com

The first account is usually an Administrator (the default role here); once
it exists, more are made from Administration → Users.

Passwords are asked for, never passed on the command line (it would sit in
the shell's history). For scripts, set NABHI_NEW_PASSWORD instead.
"""

import argparse
import getpass
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.config import get_settings
from app.db import make_engine, make_sessions
from app.demo import DEMO_ACCOUNTS, DEMO_PASSWORD, seed
from app.migrate import upgrade
from app.models import Role, User
from app.permissions import ADMINISTRATOR
from app.security import check_password_rules, hash_password


def ask_password() -> str:
    password = os.environ.get("NABHI_NEW_PASSWORD")
    if password is None:
        password = getpass.getpass("Password: ")
        if getpass.getpass("Again: ") != password:
            sys.exit("The passwords don't match.")
    problem = check_password_rules(password)
    if problem:
        sys.exit(problem)
    return password


def role_named(db, name: str) -> Role:
    role = db.scalar(select(Role).where(func.lower(Role.name) == name.lower()))
    if role is None:
        names = ", ".join(db.scalars(select(Role.name).order_by(Role.name)))
        sys.exit(f"There's no role called {name!r}. The roles are: {names}.")
    return role


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Inventory's accounts.")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="make an account")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--role", default=ADMINISTRATOR, help=f"the role's name (default {ADMINISTRATOR})")
    sub.add_parser("list", help="list accounts")
    sub.add_parser("demo", help="make the demo accounts and demo stock (development only)")
    for name in ("password", "disable", "enable"):
        sub.add_parser(name).add_argument("--email", required=True)
    args = parser.parse_args()

    engine = make_engine(get_settings().database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        if args.command == "list":
            for u in db.scalars(select(User).order_by(User.email)):
                print(f"{u.email:40} {u.full_name:30} {u.role.name:14} {'on' if u.is_active else 'off'}")
            return 0

        if args.command == "demo":
            if get_settings().is_production:
                sys.exit("Demo accounts are for development only.")
            made = 0
            for d in DEMO_ACCOUNTS:
                if db.scalar(select(User).where(func.lower(User.email) == d.email)) is None:
                    db.add(User(email=d.email, full_name=d.name, password_hash=hash_password(DEMO_PASSWORD), role_id=role_named(db, d.access).id))
                    made += 1
            db.commit()
            print(f"Made {made} demo account(s); {len(DEMO_ACCOUNTS) - made} already there. Password: {DEMO_PASSWORD}")
            if seed(db):
                db.commit()
                print("Made the demo stock: 3 warehouses, 3 suppliers, 9 products, and their movements.")
            else:
                print("Left the stock alone: there are products here already.")
            return 0

        email = args.email.strip().lower()
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if args.command == "add":
            if user is not None:
                sys.exit(f"{email} already has an account.")
            role = role_named(db, args.role)
            db.add(User(email=email, full_name=args.name.strip(), password_hash=hash_password(ask_password()), role_id=role.id))
            db.commit()
            print(f"Made {email} ({role.name}).")
            return 0
        if user is None:
            sys.exit(f"No account for {email}.")
        if args.command == "password":
            user.password_hash = hash_password(ask_password())
            user.password_changed_at = datetime.now(UTC)  # ends every session it had
        else:
            user.is_active = args.command == "enable"
        db.commit()
        print(f"{args.command}: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
