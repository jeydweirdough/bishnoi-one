"""Moves the JASMINE TASKS workbook's trackers into the admin's database:
vehicles, fuel cards, travel sponsorships and devices issued.

    uv run python -m app.tools.import_jasmine "JASMINE TASKS recorded.xlsx"            # into DATABASE_URL
    uv run python -m app.tools.import_jasmine "JASMINE TASKS recorded.xlsx" --to URL   # into another (Neon)
    uv run python -m app.tools.import_jasmine "JASMINE TASKS recorded.xlsx" --check    # says what it would do
    ... --against jasmine_parsed.json   # also checks every record in that JSON came across

It reads the workbook itself, not a copy: a JSON made from it on 2026-10-07
cut dates short ("SEPT. 5, 2"), dropped columns (the next registration, a
doctor's birthdate, quantities) and took notes under the vehicles for cars.

On the way, blanks and "nan" are empty; dates, years and peso amounts become
real ones; statuses become the lists' choices; people's names are written in
ordinary capitals (car and company names stay as written). Anything that
can't be read, and any remark beside a date ("done", "with BF sticker"), is
kept word for word in the record's notes, so nothing in the sheet is lost.
A database that already has any of these records is left alone.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime

from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import make_engine
from app.migrate import upgrade
from app.models import DeviceIssue, FleetCard, TravelSponsorship, Vehicle, guess_vehicle_kind

MONTHS = {m: i for i, names in enumerate(
    [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"), ("jul", "july"),
     ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december")], start=1) for m in names}


def text(value) -> str | None:
    """The cell as text, or None when it's empty."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = re.sub(r"\s+", " ", str(value).replace("�", "–")).strip()
    return None if s.lower() in ("", "nan", "none", "n/a", "-") else s


def as_date(value) -> date | None:
    """A date cell, or text like "October 31, 2025", "SEPT. 08, 2027", "23/06/2026, done"."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = text(value)
    if not s:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}( 00:00:00)?", s):
        return date.fromisoformat(s[:10])
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        day, month = (a, b) if a > 12 or b <= 12 else (b, a)  # day first, as the sheet writes 23/06/2026
        try:
            return date(y, month, day)
        except ValueError:
            return None
    m = re.search(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
        except ValueError:
            return None
    return None


def first_day(value, asked: date | None) -> tuple[date | None, bool]:
    """The first day of a span like "November 25 -27, 2026"; (date, whether the year was guessed from when it was asked for)."""
    s = text(value)
    if not s:
        return None, False
    if (d := as_date(s)) is not None:
        return d, False
    m = re.search(r"([A-Za-z]+)\.?\s*(\d{1,2})\b(?:.*?(\d{4}))?", s)
    if not m or m.group(1).lower() not in MONTHS:
        return None, False
    month, day = MONTHS[m.group(1).lower()], int(m.group(2))
    if m.group(3):
        return date(int(m.group(3)), month, day), False
    if asked is None:
        return None, False
    guess = date(asked.year, month, day)
    return (guess if guess >= asked else date(asked.year + 1, month, day)), True


def person(value) -> str | None:
    """'DR.JUSTINE LORENZ NATIVIDAD' -> 'Dr. Justine Lorenz Natividad'; names already in mixed case stay as written."""
    s = text(value)
    if not s or s != s.upper():
        return s
    s = re.sub(r"^DR\.?\s*", "Dr. ", s)
    return " ".join(w if w == "Dr." else "-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")) for w in s.split(" "))


def sentence(value) -> str | None:
    s = text(value)
    return s[:1].upper() + s[1:].lower() if s and s == s.upper() else s


def kept(notes: list[str]) -> str | None:
    return ("From the sheet: " + "; ".join(notes))[:500] if notes else None


def rows_of(book, sheet: str) -> list[tuple]:
    """The sheet's rows below its header, empty ones left out."""
    found = next(s for s in book.worksheets if s.title.strip().lower() == sheet.lower())
    rows = [r for r in found.iter_rows(values_only=True) if any(text(c) for c in r)]
    return rows[1:]


# --- each list -------------------------------------------------------------------------------


def vehicles(book) -> list[Vehicle]:
    out = []
    for r in rows_of(book, "VEHICLES MONITORING"):
        r = (*r, *([None] * 12))[:12]
        if not any(text(c) for c in r[1:10]):
            continue  # a note under the list ("LIST OF INSURANCE RENEWAL"), not a car
        notes: list[str] = []
        # Registration: the later of the two columns (the second holds the next renewal, or "done").
        regs = [d for d in (as_date(r[5]), as_date(r[6])) if d]
        for c in (r[5], r[6]):
            if text(c) and not isinstance(c, datetime) and (as_date(c) is None or not re.fullmatch(r"[A-Za-z]+\.? \d{1,2},? \d{4}", text(c))):
                notes.append(f"registration {text(c)!r}")
        insurance = as_date(r[7])
        if text(r[7]) and not isinstance(r[7], datetime):
            notes.append(f"insurance {text(r[7])!r}")
        if text(r[8]):
            notes.append(f"insurance: {text(r[8])}")
        pms = as_date(r[9])
        if text(r[9]) and pms is None:
            notes.append(f"PMS {text(r[9])!r}")
        if text(r[11]):
            notes.append(f"parts: {text(r[11])}")
        year = r[2] if isinstance(r[2], (int, float)) else None
        out.append(Vehicle(
            name=text(r[0]) or "Unnamed vehicle", kind=guess_vehicle_kind(text(r[0]), text(r[1])), plate=text(r[1]), year_model=int(year) if year else None, color=text(r[3]),
            owner_name=text(r[4]), registration_due=max(regs) if regs else None, insurance_due=insurance, pms_due=pms,
            fleet_card=text(r[10]), notes=kept(notes),
        ))
    return out


FLEET_STATUS = {"handed over": "handed_over", "handed over to hr": "with_hr", "processing": "processing", "returned": "returned"}


def fleet_cards(book) -> list[FleetCard]:
    out = []
    for r in rows_of(book, "SALES PERSON_FLEETCARD"):
        r = (*r, *([None] * 10))[:10]
        notes: list[str] = []
        allowance = r[3]
        amount = float(allowance) if isinstance(allowance, (int, float)) else None
        if amount is None and text(allowance) and re.fullmatch(r"[\d,]+(\.\d+)?", text(allowance)):
            amount = float(text(allowance).replace(",", ""))
        raw_status = (text(r[8]) or "").lower()
        if raw_status and raw_status not in FLEET_STATUS:
            notes.append(f"status {raw_status!r}")
        remark = (text(r[9]) or "").lower()
        if remark not in ("active", "blocked", ""):
            notes.append(remark.capitalize())
        out.append(FleetCard(
            requested_on=as_date(r[0]), holder_name=person(r[1]) or "Unnamed", company_name=text(r[2]),
            monthly_allowance=amount, allowance_note=None if amount is not None else sentence(allowance),
            fuel_type=sentence(r[4]), plate=text(r[5]), conduction_sticker=text(r[6]), vehicle_unit=text(r[7]),
            status=FLEET_STATUS.get(raw_status, "processing"), card_state="blocked" if remark == "blocked" else "active", notes=kept(notes),
        ))
    return out


TRAVEL_STATUS = {"approved": "approved", "booked": "booked", "for processing": "for_processing", "for approval": "for_approval", "cancelled": "cancelled"}


def sponsorships(book) -> list[TravelSponsorship]:
    out = []
    for r in rows_of(book, "FLIGHT AND HOTEL SPONSORSHIP"):
        r = (*r, *([None] * 11))[:11]
        notes: list[str] = []
        asked = as_date(r[0])
        flight = "flight" in (text(r[7]) or "").lower()
        when = text(r[6]) if flight else text(r[4])
        where = text(r[5])
        if flight and when and (m := re.search(r"\(([^)]*)\)", when)):
            where = m.group(1).strip()
        starts, guessed = first_day(when, asked)
        if guessed:
            notes.append(f"no year on {when!r}: taken as {starts.year}, after it was asked for")
        raw_status = (text(r[8]) or "").lower()
        if raw_status and raw_status not in TRAVEL_STATUS:
            notes.append(f"status {raw_status!r}")
        out.append(TravelSponsorship(
            requested_on=asked, rep_name=person(r[1]) or "Unknown", doctor_name=person(r[2]) or "Unknown", doctor_birthdate=as_date(r[3]),
            kind="flight" if flight else "hotel", travel_dates=when, starts_on=starts, hotel_or_flight=where,
            status=TRAVEL_STATUS.get(raw_status, "for_approval"), approved_on=as_date(r[10]), next_step=sentence(r[9]), notes=kept(notes),
        ))
    return out


CONDITION = {"brand new": "brand_new", "repaired": "repaired", "old": "used", "used": "used"}


def devices(book) -> tuple[list[DeviceIssue], list[str]]:
    """The devices handed out; and the stock notes under the list ("Received 7 pcs phone"), which aren't hand-outs."""
    out, stock = [], []
    for r in rows_of(book, "LAPTOPMOBILE PHONE MONITORING"):
        r = (*r, *([None] * 10))[:10]
        if isinstance(r[0], str) and not any(text(c) for c in r[1:]):
            stock.append(text(r[0]))
            continue

        def item(name, qty) -> str | None:
            n = text(name)
            return f"{n} ×{int(qty)}" if n and isinstance(qty, (int, float)) and qty > 1 else n

        laptop, phone, sim = item(r[1], r[2]), item(r[3], r[4]), item(r[5], r[6])
        notes: list[str] = []
        raw = (text(r[8]) or "").lower()
        if raw and raw not in CONDITION:
            notes.append(f"remarks {raw!r}")
        if not (laptop or phone or sim):
            notes.append("no laptop, phone or SIM listed")
        out.append(DeviceIssue(issued_on=as_date(r[0]), issued_to=text(r[7]) or "Unnamed", laptop=laptop, phone=phone, sim=sim,
                               condition=CONDITION.get(raw, "brand_new"), signed_by=person(r[9]), notes=kept(notes)))
    return out, stock


def missing_from(built: dict[type, list], against: dict) -> list[str]:
    """Each record in the JSON that has no match among what's being imported."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", (text(s) or "").lower())  # noqa: E731
    have = {
        "vehicles": {norm(v.plate) for v in built[Vehicle]},
        "fleetcards": {(norm(c.holder_name), str(c.requested_on)) for c in built[FleetCard]},
        "sponsorships": {(norm(t.doctor_name), str(t.requested_on)) for t in built[TravelSponsorship]},
        "devices": {(norm(d.issued_to), str(d.issued_on)) for d in built[DeviceIssue]},
    }
    out = []
    for row in against.get("vehicles", []):
        if text(row.get("plate")) and norm(row["plate"]) not in have["vehicles"]:
            out.append(f"vehicle {row.get('car_name')} {row.get('plate')}")
        elif not text(row.get("plate")) and text(row.get("renewal")) is None and text(row.get("model")) is None:
            continue  # the JSON's notes taken for cars
    for row in against.get("fleetcards", []):
        if (norm(person(row.get("name"))), str(as_date(row.get("req_date")))) not in have["fleetcards"]:
            out.append(f"fuel card {row.get('name')} {row.get('req_date')}")
    for row in against.get("sponsorships", []):
        if (norm(person(row.get("doctor_name"))), str(as_date(row.get("req_date")))) not in have["sponsorships"]:
            out.append(f"sponsorship {row.get('doctor_name')} {row.get('req_date')}")
    for row in against.get("devices", []):
        if (norm(row.get("person")), str(as_date(row.get("date")))) not in have["devices"]:
            out.append(f"device {row.get('person')} {row.get('date')}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("workbook")
    parser.add_argument("--to", help="a database address; DATABASE_URL when not given")
    parser.add_argument("--check", action="store_true", help="read and clean only; save nothing")
    parser.add_argument("--against", help="a JSON made from the workbook: says which of its records wouldn't come across")
    args = parser.parse_args(argv)
    book = load_workbook(args.workbook, read_only=True, data_only=True)
    device_rows, stock = devices(book)
    built = {Vehicle: vehicles(book), FleetCard: fleet_cards(book), TravelSponsorship: sponsorships(book), DeviceIssue: device_rows}
    for model, rows in built.items():
        print(f"{model.__tablename__}: {len(rows)} records, {sum(1 for r in rows if r.notes)} with something kept in their notes")
    if stock:
        print(f"Left out, as stock notes and not hand-outs: {stock}")
    if args.against:
        missing = missing_from(built, json.load(open(args.against, encoding="utf-8")))
        print("Every record in the JSON is here." if not missing else f"Not found ({len(missing)}): {missing}")
        if missing:
            return 2
    if args.check:
        for model, rows in built.items():
            for r in rows:
                if r.notes:
                    print(f"  {model.__tablename__}: {r.notes}")
        return 0
    engine = make_engine(args.to or get_settings().database_url)
    upgrade(engine)
    with Session(engine) as db:
        already = {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in built}
        if any(already.values()):
            print(f"Left alone: this database already has some of these records ({already}).")
            return 1
        for rows in built.values():
            db.add_all(rows)
        db.commit()
        print("Saved:", {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in built})
    return 0


if __name__ == "__main__":
    sys.exit(main())
