"""Dated tax rates in this app's database.

Each pack lists its rates with the days they apply. On start, any pack rate
not yet here is added, so updating a pack is enough to bring in a new rate.
A rate entered by an admin (a change in the law, ahead of an update) is kept
beside them and wins from its first day.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import TaxProfile, TaxRate
from app.tax.engine import RateLookup
from app.tax.packs import PACKS


def seed(sessions: sessionmaker[Session]) -> None:
    """Every pack's rates, and the company's registration row, if missing."""
    with sessions() as db:
        have = set(db.execute(select(TaxRate.country, TaxRate.code, TaxRate.valid_from)).all())
        for country, pack in PACKS.items():
            for code, bp, start, end, basis in pack.RATES:
                start_on = date.fromisoformat(start)
                if (country, code, start_on) not in have:
                    db.add(TaxRate(
                        country=country, code=code, rate_bp=bp, valid_from=start_on,
                        valid_to=date.fromisoformat(end) if end else None, source="pack", basis=basis,
                    ))
        if db.get(TaxProfile, 1) is None:
            db.add(TaxProfile(id=1))
        db.commit()


def lookup(db: Session, country: str) -> RateLookup:
    """The rate for a code on a day: the latest-starting row that covers it."""
    rows = db.scalars(select(TaxRate).where(TaxRate.country == country).order_by(TaxRate.valid_from.desc())).all()

    def rate(code: str, on: date) -> int | None:
        for r in rows:
            if r.code == code and r.valid_from <= on and (r.valid_to is None or on <= r.valid_to):
                return r.rate_bp
        return None

    return rate


def change(db: Session, country: str, code: str, rate_bp: int, valid_from: date, basis: str | None, by_id: str) -> TaxRate:
    """A new rate from a day on. The rate in force until then ends the day
    before; one that starts later stays as it is."""
    current = db.scalars(
        select(TaxRate)
        .where(TaxRate.country == country, TaxRate.code == code, TaxRate.valid_from < valid_from)
        .order_by(TaxRate.valid_from.desc())
    ).first()
    if current is not None and (current.valid_to is None or current.valid_to >= valid_from):
        current.valid_to = valid_from - timedelta(days=1)
    later = db.scalars(
        select(TaxRate).where(TaxRate.country == country, TaxRate.code == code, TaxRate.valid_from > valid_from).order_by(TaxRate.valid_from)
    ).first()
    new = TaxRate(
        country=country, code=code, rate_bp=rate_bp, valid_from=valid_from,
        valid_to=later.valid_from - timedelta(days=1) if later else None, source="admin", basis=basis, created_by_id=by_id,
    )
    db.add(new)
    return new
