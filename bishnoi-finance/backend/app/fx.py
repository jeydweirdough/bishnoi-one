"""Foreign currency (feature plan step 16c, 2026-10-29): USD (or any currency) supplier bills at the day's rate.

Finance records the rate for a day (pesos per unit, kept as rate x 10,000 in whole numbers so money stays exact).
A foreign bill's lines are in its currency; it's booked in pesos at the rate on the bill's day. Paying it later
at that day's rate makes a difference: what we paid in pesos against what the bill was booked at. Paying fewer
pesos is an exchange gain, more is a loss; each goes to its account (Default accounts).
"""

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExchangeRate

BASE = "PHP"
SCALE = 10_000
# A rate older than this isn't used for a day without its own.
STALE_DAYS = 7


def to_pesos(amount: int, rate_e4: int) -> int:
    """An amount in centavos of the foreign currency, in peso centavos, rounded half up (away from zero)."""
    sign = -1 if amount < 0 else 1
    return sign * ((2 * abs(amount) * rate_e4 + SCALE) // (2 * SCALE))


def rate_e4_of(value: float | str) -> int:
    return round(float(value) * SCALE)


def rate_on(db: Session, currency: str, on: date) -> int | None:
    """The rate for the day, or the latest within a week before it."""
    found = db.scalar(select(ExchangeRate).where(ExchangeRate.currency == currency, ExchangeRate.on <= on, ExchangeRate.on >= on - timedelta(days=STALE_DAYS))
                      .order_by(ExchangeRate.on.desc()))
    return found.rate_e4 if found else None


def need_rate(db: Session, currency: str, on: date, given: float | None, field: str) -> int:
    """The rate given, else the one on record for the day; refused when there's neither."""
    if given is not None:
        if given <= 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", field], "msg": "Enter a rate above zero."}])
        return rate_e4_of(given)
    found = rate_on(db, currency, on)
    if found is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", field],
                            "msg": f"Enter the {currency} rate for {on:%d %b %Y}, or record it under Banking, Exchange rates."}])
    return found
