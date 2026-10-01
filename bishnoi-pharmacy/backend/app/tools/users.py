"""The Pharmacy's accounts, from the command line. Most of this is also in
Administration → Users; this is for the first account, and for scripts.

    uv run python -m app.tools.users add --email ana@example.com --name "Ana Reyes" --admin
    uv run python -m app.tools.users add --email ben@example.com --name "Ben Cruz" --role "Pharmacist" --license PRC-0012345
    uv run python -m app.tools.users list
    uv run python -m app.tools.users demo        # the demo accounts and records (development)
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
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import next_number, today
from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.demo import (
    DEMO_ACCOUNTS,
    DEMO_BATCHES,
    DEMO_BRANDS,
    DEMO_CATEGORIES,
    DEMO_MEDICINES,
    DEMO_PASSWORD,
    DEMO_PATIENTS,
    DEMO_PRESCRIPTIONS,
    DEMO_SUPPLIERS,
)
from app.migrate import upgrade
from app.models import CHECK_KEYS, Batch, Brand, Category, Medicine, Patient, Prescription, PrescriptionItem, Receiving, Role, Supplier, User
from app.permissions import ADMINISTRATOR, ASSISTANT
from app.security import check_password_rules, hash_password
from app.stock import move

TOOL = "users tool"  # how the activity log names changes made from here


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


def make_demo(db: Session) -> None:
    if get_settings().is_production:
        sys.exit("Demo accounts are for development only.")
    made = 0
    for d in DEMO_ACCOUNTS:
        role = role_named(db, d.access)
        user = db.scalar(select(User).where(func.lower(User.email) == d.email))
        if user is None:
            user = User(email=d.email, full_name=d.name, password_hash=hash_password(DEMO_PASSWORD), role_id=role.id, license_no=d.license_no)
            db.add(user)
            db.flush()
            audit(db, TOOL, "user.created", target=user.email, target_type="user", target_id=user.id)
            made += 1
        elif user.role_id != role.id:
            # A demo account from before roles (Orbit Pharmacy) gets its own.
            user.role_id, user.license_no = role.id, d.license_no
            audit(db, TOOL, "user.updated", target=user.email, target_type="user", target_id=user.id, fields=["roleId"])
    db.commit()
    print(f"Demo accounts: {made} made, {len(DEMO_ACCOUNTS) - made} already here. Password: {DEMO_PASSWORD}")
    make_demo_records(db)


def make_demo_records(db: Session) -> None:
    """A catalogue, suppliers, stock, patients and prescriptions in every state.
    Only into a database with no medicines yet, so it never doubles anything up."""
    if db.scalar(select(func.count()).select_from(Medicine)):
        print("Demo records: skipped, there are medicines already.")
        return
    settings = get_settings()
    on = today(settings)
    pharmacist = db.scalar(select(User).where(User.email == DEMO_ACCOUNTS[0].email))
    assistant = db.scalar(select(User).where(User.email == DEMO_ACCOUNTS[1].email))

    categories = {name: Category(name=name) for name in DEMO_CATEGORIES}
    brands = {name: Brand(name=name, manufacturer=maker) for name, maker in DEMO_BRANDS}
    db.add_all([*categories.values(), *brands.values()])
    medicines: dict[str, Medicine] = {}
    for code, generic, brand, category, strength, form, unit, rx_class, pesos, reorder in DEMO_MEDICINES:
        medicines[code] = Medicine(
            code=code, generic_name=generic, brand=brands[brand], category=categories[category], strength=strength,
            dosage_form=form, unit=unit, rx_class=rx_class, price_centavos=round(pesos * 100), reorder_level=reorder,
        )
    db.add_all(medicines.values())
    suppliers = {name: Supplier(name=name, contact_person=who, phone=phone, email=email) for name, who, phone, email in DEMO_SUPPLIERS}
    db.add_all(suppliers.values())
    db.flush()

    # One delivery per supplier, a month ago, carrying their batches.
    deliveries = {}
    for name, supplier in suppliers.items():
        deliveries[name] = Receiving(
            number=next_number(db, "RC", settings), supplier_id=supplier.id, reference=f"INV-{supplier.name[:3].upper()}-1001",
            received_on=on - timedelta(days=30), received_by_id=pharmacist.id,
        )
    db.add_all(deliveries.values())
    db.flush()
    for code, lot, supplier, days, qty, cost in DEMO_BATCHES:
        batch = Batch(
            medicine_id=medicines[code].id, lot_no=lot, supplier_id=suppliers[supplier].id, receiving_id=deliveries[supplier].id,
            expires_on=on + timedelta(days=days), cost_centavos=round(cost * 100), qty_received=qty, qty_on_hand=0,
        )
        db.add(batch)
        db.flush()
        move(db, batch, qty, "receive", by=pharmacist, reference=deliveries[supplier].number)

    patients: dict[str, Patient] = {}
    for name, kind, born, sex, phone, allergies in DEMO_PATIENTS:
        patients[name] = Patient(
            kind=kind, full_name=name, birth_date=date.fromisoformat(born) if born else None, sex=sex, phone=phone, allergies=allergies,
        )
    db.add_all(patients.values())
    db.flush()

    now = datetime.now(UTC)
    for patient, prescriber, licence, clinic, days_ago, status, items in DEMO_PRESCRIPTIONS:
        received = now - timedelta(days=days_ago, hours=2)
        checked = status != "received"
        rx = Prescription(
            number=next_number(db, "RX", settings), patient_id=patients[patient].id, prescriber_name=prescriber,
            prescriber_license=licence, prescriber_clinic=clinic, prescribed_on=on - timedelta(days=days_ago),
            status=status, received_by_id=assistant.id, received_at=received,
            checks={k: status == "verified" or (status == "pending" and n < 5) for n, k in enumerate(CHECK_KEYS)} if checked else {},
            checked_by_id=pharmacist.id if checked else None, checked_at=received + timedelta(hours=1) if checked else None,
            verification_notes="Dose unclear: call Dr. Ramos to confirm the strength (patient is allergic to penicillin)."
            if status == "needs_clarification" else None,
            items=[
                PrescriptionItem(position=n, written_as=written, medicine_id=medicines[code].id if checked else None, quantity=qty, directions=how)
                for n, (written, code, qty, how) in enumerate(items)
            ],
        )
        db.add(rx)
    summary = (
        f"{len(medicines)} medicines, {len(suppliers)} suppliers, {len(DEMO_BATCHES)} batches, "
        f"{len(patients)} patients and customers, {len(DEMO_PRESCRIPTIONS)} prescriptions"
    )
    audit(db, TOOL, "demo.records_made", target=summary[:200])
    db.commit()
    print(f"Demo records: {summary}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the Pharmacy's accounts.")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="make an account")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--admin", action="store_true", help=f"give them the {ADMINISTRATOR} role")
    add.add_argument("--role", help=f"the role's name (default: {ASSISTANT})")
    add.add_argument("--license", help="a pharmacist's licence number")
    sub.add_parser("list", help="list accounts")
    sub.add_parser("demo", help="make the demo accounts and records (development only)")
    for name in ("password", "disable", "enable"):
        sub.add_parser(name).add_argument("--email", required=True)
    args = parser.parse_args()

    engine = make_engine(get_settings().database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        if args.command == "list":
            for u in db.scalars(select(User).order_by(User.email)):
                print(f"{u.email:34} {u.full_name:22} {u.role.name:20} {'on' if u.is_active else 'off'}")
            return 0
        if args.command == "demo":
            make_demo(db)
            return 0

        email = args.email.strip().lower()
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if args.command == "add":
            if user is not None:
                sys.exit(f"{email} already has an account.")
            role = role_named(db, ADMINISTRATOR if args.admin else (args.role or ASSISTANT))
            user = User(email=email, full_name=args.name.strip(), password_hash=hash_password(ask_password()), role_id=role.id, license_no=args.license)
            db.add(user)
            db.flush()
            audit(db, TOOL, "user.created", target=user.email, target_type="user", target_id=user.id)
            db.commit()
            print(f"Made {email} ({role.name}).")
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
