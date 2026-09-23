"""This app's accounts, from the command line. There is no sign-up page.

    uv run python -m app.tools.users add --email ana@example.com --name "Ana Reyes" [--admin]
    uv run python -m app.tools.users list
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

from app.config import get_settings
from app.db import create_tables, make_engine, make_sessions
from app.models import User
from app.security import check_password_rules, hash_password


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage this app's accounts.")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="make an account")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--admin", action="store_true", help="can run this app's settings")
    sub.add_parser("list", help="list accounts")
    for name in ("password", "disable", "enable"):
        sub.add_parser(name).add_argument("--email", required=True)
    args = parser.parse_args()

    engine = make_engine(get_settings().database_url)
    create_tables(engine)
    with make_sessions(engine)() as db:
        if args.command == "list":
            for u in db.scalars(select(User).order_by(User.email)):
                print(f"{u.email:40} {u.full_name:30} {u.role:7} {'on' if u.is_active else 'off'}")
            return 0

        email = args.email.strip().lower()
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if args.command == "add":
            if user is not None:
                sys.exit(f"{email} already has an account.")
            db.add(User(email=email, full_name=args.name.strip(), password_hash=hash_password(ask_password()), role="admin" if args.admin else "member"))
            db.commit()
            print(f"Made {email}.")
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
