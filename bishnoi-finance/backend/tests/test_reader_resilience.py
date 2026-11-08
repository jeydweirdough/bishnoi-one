"""The official Zoho reader stopped on 2026-10-28 when Neon dropped its connection:
the pg8000 setup relied on pool_pre_ping, which only replaces a connection when
SQLAlchemy recognises the error as a disconnect, and a plain socket TimeoutError
isn't one; and the worker treated a database/network error as fatal.

Now a dead pooled connection is replaced whatever the driver raises, and such an
error ends only that cycle."""

import os
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import QueuePool

from app import db as app_db
from app.postgres_driver import python_engine
from app.tools import sync_zoho_month

POSTGRES_ADMIN = os.environ.get("FINANCE_TEST_POSTGRES_ADMIN_URL")


class Dropped:
    """A DB-API connection whose server has gone: its next statement times out."""

    def __init__(self, real):
        self.real, self.dead = real, False

    def cursor(self):
        cursor = self.real.cursor()
        if self.dead:
            def timed_out(*_):
                raise TimeoutError("The read operation timed out")
            return SimpleNamespace(execute=timed_out, close=cursor.close)
        return cursor

    def __getattr__(self, name):
        return getattr(self.real, name)


def test_a_dropped_connection_is_replaced_even_when_the_driver_raises_a_plain_timeout(tmp_path, monkeypatch):
    made = []

    def connect():
        made.append(Dropped(sqlite3.connect(tmp_path / "x.db", check_same_thread=False)))
        return made[-1]

    engine = create_engine("sqlite://", creator=connect, poolclass=QueuePool)
    app_db.ping_when_idle(engine)
    monkeypatch.setattr(app_db, "IDLE_BEFORE_PING", 0)  # every returned connection counts as idle
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    made[0].dead = True
    with engine.connect() as c:  # the ping times out: a fresh connection is used instead of failing
        assert c.execute(text("SELECT 42")).scalar() == 42
    assert len(made) == 2
    engine.dispose()


def test_the_neon_setup_uses_that_ping_not_pool_pre_ping():
    engine = python_engine("postgresql://user:secret@db.invalid/finance?sslmode=require")
    assert event.contains(engine, "checkout", app_db._ping_if_idle)
    assert event.contains(engine, "checkin", app_db._returned)
    assert not engine.pool._pre_ping
    engine.dispose()


@pytest.fixture
def one_cycle(monkeypatch):
    """The reader's cycle with Zoho and the lock stood in for; `outcome` decides what the sync does."""
    outcome = {}

    @contextmanager
    def no_lock(settings):
        yield

    def sync(*_, **__):
        if "raise" in outcome:
            raise outcome["raise"]
        return {"mode": "month-sync"}

    monkeypatch.setattr(sync_zoho_month, "sync_lock", no_lock)
    monkeypatch.setattr(sync_zoho_month, "ZohoReader", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(sync_zoho_month, "month_window", lambda: (None, None))
    monkeypatch.setattr(sync_zoho_month, "sync_month", sync)
    args = SimpleNamespace(requests=60, details=20, daily_limit=500, interval=300, work_start=7, work_end=16)
    return outcome, (lambda: sync_zoho_month.cycle(None, None, args))


@pytest.mark.parametrize("error", [
    TimeoutError("The read operation timed out"),
    ConnectionResetError(10054, "An existing connection was forcibly closed by the remote host"),
    OperationalError("SELECT 1", {}, Exception("server closed the connection to postgres://u:p@host/db")),
])
def test_a_database_or_network_failure_pauses_one_cycle_and_the_next_one_runs(one_cycle, capsys, error):
    outcome, cycle = one_cycle
    outcome["raise"] = error
    assert cycle() is False
    printed = capsys.readouterr().out
    assert type(error).__name__ in printed and "postgres://" not in printed  # its kind, never its details
    del outcome["raise"]
    assert cycle() is True


def test_an_unexpected_error_still_stops_the_reader(one_cycle):
    """Only database/network failures are waited out; a bug must not be retried silently forever."""
    outcome, cycle = one_cycle
    outcome["raise"] = KeyError("invoice_id")
    with pytest.raises(KeyError):
        cycle()


@pytest.mark.skipif(not POSTGRES_ADMIN, reason="FINANCE_TEST_POSTGRES_ADMIN_URL is not set")
def test_on_postgresql_a_connection_the_server_ended_is_replaced(monkeypatch):
    """The real driver path: the server ends the pooled connection, the next checkout still works."""
    engine = app_db.make_engine(POSTGRES_ADMIN, postgres_driver="pg8000")
    monkeypatch.setattr(app_db, "IDLE_BEFORE_PING", 0)
    try:
        with engine.connect() as c:
            gone = c.execute(text("SELECT pg_backend_pid()")).scalar()
        killer = app_db.make_engine(POSTGRES_ADMIN, postgres_driver="pg8000")
        with killer.connect() as k:
            assert k.execute(text("SELECT pg_terminate_backend(:p)"), {"p": gone}).scalar() is True
        killer.dispose()
        with engine.connect() as c:
            assert c.execute(text("SELECT pg_backend_pid()")).scalar() != gone
            assert c.execute(text("SELECT current_setting('transaction_read_only')")).scalar() == "off"
    finally:
        engine.dispose()
