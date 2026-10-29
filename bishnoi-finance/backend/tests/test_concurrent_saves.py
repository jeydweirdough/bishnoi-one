"""Two people saving the same money step at the same moment: only one goes
through; the other is refused plainly, as if they'd been a second later.

Each test holds the first save partway (after its checks, before it writes),
sends the second, waits for it, then lets the first finish. Without locks the
second passes the same checks on the same old state (a voucher released twice,
two vouchers filling one bill, two payments both fitting in what was owed, two
entries with one number); with them it waits, then sees the first's result.

Runs on SQLite every time. Set FINANCE_TEST_POSTGRES_ADMIN_URL (an address on a
PostgreSQL server whose user may create databases; never the official one) to
also run it on PostgreSQL: each test makes its own throwaway database there and
drops it afterwards.
"""

import os
import threading
import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from app import ledger
from app.config import Settings
from app.db import make_engine
from app.main import create_app
from app.models import JournalEntry, User
from app.routers import invoices, vouchers
from app.routers.auth import attempts
from app.security import hash_password

from .test_auth import PASSWORD
from .test_invoices import issued, ready
from .test_payables import account
from .test_tax_api import ana, client  # noqa: F401 (fixtures)
from .test_vouchers import prepare, ready_bill, team  # noqa: F401 (fixtures)

POSTGRES_ADMIN = os.environ.get("FINANCE_TEST_POSTGRES_ADMIN_URL")
BACKENDS = ["sqlite", pytest.param("postgresql", marks=pytest.mark.skipif(not POSTGRES_ADMIN, reason="FINANCE_TEST_POSTGRES_ADMIN_URL is not set"))]


def seeded(settings: Settings):
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD)))
        db.commit()
    return app


@pytest.fixture(params=BACKENDS)
def app(request, tmp_path):
    attempts.clear()
    base = {"_env_file": None, "allowed_hosts": ["testserver"]}
    if request.param == "sqlite":
        yield seeded(Settings(**base, database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}"))
        return
    admin_url = make_url(POSTGRES_ADMIN)
    driver = "pg8000" if admin_url.drivername.endswith("pg8000") else "psycopg"
    name = f"finance_concurrency_{uuid.uuid4().hex[:12]}"
    def admin(sql: str) -> None:
        """One statement on a fresh connection outside any transaction (CREATE/DROP DATABASE need that),
        made through the app's own connection setup (app/db.py) so the address's TLS settings apply."""
        engine = make_engine(POSTGRES_ADMIN, postgres_driver=driver)
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
                c.execute(text(sql))
        finally:
            engine.dispose()

    admin(f'CREATE DATABASE "{name}"')
    try:
        url = admin_url.set(database=name).render_as_string(hide_password=False)
        built = seeded(Settings(**base, database_url=url, postgres_driver=driver))
        yield built
        built.state.sessions.kw["bind"].dispose()
    finally:
        admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def race(monkeypatch, module, name: str, first: Callable, second: Callable) -> tuple:
    """Run `first` until it reaches module.name (its checks done), run `second`
    meanwhile, then let `first` finish. Returns both responses."""
    real = getattr(module, name)
    entered, go = threading.Event(), threading.Event()
    calls = []

    def held(*args, **kwargs):
        result = real(*args, **kwargs)
        calls.append(1)
        if len(calls) == 1:
            entered.set()
            assert go.wait(20), "the first save was never let go"
        return result

    monkeypatch.setattr(module, name, held)
    out = {}
    a = threading.Thread(target=lambda: out.setdefault("first", first()))
    a.start()
    assert entered.wait(20), "the first save never reached its checks"
    b = threading.Thread(target=lambda: out.setdefault("second", second()))
    b.start()
    b.join(3)  # without locks it finishes now, on the old state; with them it waits for the first
    go.set()
    a.join(30)
    b.join(30)
    return out["first"], out["second"]


def entries(app, source: str) -> list[str]:
    with app.state.sessions() as db:
        return list(db.scalars(select(JournalEntry.number).where(JournalEntry.source == source)))


def test_a_voucher_released_twice_at_once_pays_once(client, ana, team, app, monkeypatch):  # noqa: F811
    s, b = ready_bill(client, team)
    v = prepare(client, team["aubrey"], s, [{"billId": b["id"], "amountCentavos": 500_000}])
    assert client.post(f"/finance/vouchers/{v['id']}/submit", json={}, headers=team["aubrey"]).status_code == 200
    release = lambda: client.post(f"/finance/vouchers/{v['id']}/release", json={"paidOn": "2026-10-02", "bankReference": "BDO-1"}, headers=team["cristal"])  # noqa: E731
    first, second = race(monkeypatch, vouchers, "post", release, release)
    assert sorted([first.status_code, second.status_code]) == [200, 409], (first.text, second.text)
    assert client.get(f"/finance/bills/{b['id']}", headers=ana).json()["paidCentavos"] == 500_000
    assert len(entries(app, "voucher")) == 1


def test_two_vouchers_made_at_once_cannot_both_take_the_whole_bill(client, ana, team, monkeypatch):  # noqa: F811
    s, b = ready_bill(client, team)  # 11,100.00 left to pay
    aubrey = team["aubrey"]
    whole = lambda: client.post("/finance/vouchers", json={"supplierId": s["id"], "method": "bank", "paidFromId": account(client, aubrey, "1010"),  # noqa: E731
                                                           "lines": [{"billId": b["id"], "amountCentavos": 1_110_000}]}, headers=aubrey)
    first, second = race(monkeypatch, vouchers, "set_aside", whole, whole)
    assert sorted([first.status_code, second.status_code]) == [201, 422], (first.text, second.text)
    refused = first if first.status_code == 422 else second
    assert "set aside in another voucher" in refused.text


def test_two_payments_at_once_cannot_both_settle_one_invoice(client, ana, app, monkeypatch):  # noqa: F811
    ready(client, ana)
    inv = issued(client, ana)  # 2,240.00
    pay = lambda: client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": inv["date"], "amountCentavos": 224000, "method": "cash"}, headers=ana)  # noqa: E731
    first, second = race(monkeypatch, invoices, "post", pay, pay)
    assert sorted([first.status_code, second.status_code]) == [201, 422], (first.text, second.text)
    assert client.get(f"/finance/invoices/{inv['id']}", headers=ana).json()["paidCentavos"] == 224000
    assert len([n for n in entries(app, "invoice")]) == 2  # the sale and one payment


def test_entries_saved_at_once_get_different_numbers(client, ana, app, monkeypatch):  # noqa: F811
    ready(client, ana)
    one, two = issued(client, ana), issued(client, ana, customerName="Watsons BGC")
    pay = lambda inv: (lambda: client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": inv["date"], "amountCentavos": 1000, "method": "cash"}, headers=ana))  # noqa: E731
    first, second = race(monkeypatch, ledger, "next_number", pay(one), pay(two))
    assert (first.status_code, second.status_code) == (201, 201), (first.text, second.text)
    numbers = entries(app, "invoice")
    assert len(numbers) == 4 and len(set(numbers)) == 4


def test_a_voucher_and_its_bill_are_not_double_paid_by_a_second_supplier_step(client, ana, team, app, monkeypatch):  # noqa: F811
    """Two vouchers for one bill, each for half, released at once: both fit, the bill is paid in full once."""
    s, b = ready_bill(client, team)
    halves = [prepare(client, team["aubrey"], s, [{"billId": b["id"], "amountCentavos": 555_000}]) for _ in range(2)]
    for v in halves:
        assert client.post(f"/finance/vouchers/{v['id']}/submit", json={}, headers=team["aubrey"]).status_code == 200
    release = lambda v: (lambda: client.post(f"/finance/vouchers/{v['id']}/release", json={"paidOn": "2026-10-02", "bankReference": f"BDO-{v['number']}"}, headers=team["cristal"]))  # noqa: E731
    first, second = race(monkeypatch, vouchers, "post", release(halves[0]), release(halves[1]))
    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert client.get(f"/finance/bills/{b['id']}", headers=ana).json()["paidCentavos"] == 1_110_000
    numbers = entries(app, "voucher")
    assert len(numbers) == 2 and len(set(numbers)) == 2
