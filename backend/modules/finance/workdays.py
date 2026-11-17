"""Which days the office works: Monday to Saturday, except Philippine holidays.

Decided 2026-10-22 (Plans/Plan - Philippine holidays): the office works Monday
to Saturday; regular holidays and special non-working days are both days off;
special working days (e.g. the EDSA anniversary) are worked.

The holidays come from the `holidays` library (its Philippine calendar, from the
proclamations and Republic Acts, offline: nothing is asked of the internet). A
new year's proclamation arrives with a library update (uv.lock pins the version).
Days the company decides itself (a typhoon suspension, an outing) aren't here
yet: a short list kept in Finance is planned for those.
"""

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import holidays

SUNDAY = 6


@lru_cache(maxsize=16)
def days_off(year: int) -> frozenset[date]:
    """Regular holidays and special non-working days that year (the library's
    "public" category; special working days are a separate category, left out)."""
    return frozenset(holidays.country_holidays("PH", years=year))


def is_workday(day: date) -> bool:
    return day.weekday() != SUNDAY and day not in days_off(day.year)


def next_workday(day: date) -> date:
    """The first working day after this one."""
    day += timedelta(days=1)
    while not is_workday(day):
        day += timedelta(days=1)
    return day


def workdays_before(day: date, n: int) -> date:
    """n working days before this day (0: the day itself). A reminder for Monday
    the 26th set 1 working day before falls on Saturday the 24th."""
    while n > 0:
        day -= timedelta(days=1)
        if is_workday(day):
            n -= 1
    return day


def holidays_between(since: date, until: date) -> list[tuple[date, str]]:
    """Philippine days off in this span, with their names, for the calendar."""
    found = []
    for year in range(since.year, until.year + 1):
        found += [(d, name) for d, name in holidays.country_holidays("PH", years=year).items() if since <= d <= until]
    return sorted(found)


def one_workday_later(moment: datetime, tz: str) -> datetime:
    """The same time of day on the next working day, in the company's time zone.
    Posted Saturday 9:00 -> Monday 9:00; Thursday 11 June 2026 -> Saturday 13
    June (the 12th is Independence Day)."""
    local = moment.astimezone(ZoneInfo(tz))
    return datetime.combine(next_workday(local.date()), time(local.hour, local.minute, local.second), tzinfo=local.tzinfo)
