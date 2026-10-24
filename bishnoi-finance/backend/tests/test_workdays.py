"""Working days: Monday to Saturday, except Philippine holidays (decided 2026-10-22)."""

from datetime import UTC, date, datetime

from app.workdays import is_workday, next_workday, one_workday_later

MANILA = "Asia/Manila"


def test_monday_to_saturday_are_worked_sunday_is_not():
    assert [is_workday(date(2026, 10, d)) for d in range(19, 26)] == [True, True, True, True, True, True, False]  # Mon 19 .. Sun 25


def test_regular_holidays_and_special_non_working_days_are_off():
    assert not is_workday(date(2026, 12, 25))  # Christmas Day (regular)
    assert not is_workday(date(2026, 6, 12))  # Independence Day (regular)
    assert not is_workday(date(2026, 12, 24))  # Christmas Eve (special non-working)
    assert not is_workday(date(2026, 4, 4))  # Black Saturday


def test_special_working_days_are_worked():
    assert is_workday(date(2026, 2, 25))  # EDSA anniversary: a special working day


def test_the_next_working_day_skips_sundays_and_holidays():
    assert next_workday(date(2026, 10, 24)) == date(2026, 10, 26)  # Saturday -> Monday
    assert next_workday(date(2026, 6, 11)) == date(2026, 6, 13)  # Thursday -> Saturday (Friday the 12th is off)
    assert next_workday(date(2026, 12, 23)) == date(2026, 12, 26)  # past Christmas Eve and Christmas Day


def test_one_working_day_later_keeps_the_time_in_manila():
    saturday_9am = datetime(2026, 10, 24, 1, 0, tzinfo=UTC)  # 9:00 in Manila
    later = one_workday_later(saturday_9am, MANILA)
    assert (later.date(), later.hour) == (date(2026, 10, 26), 9)
