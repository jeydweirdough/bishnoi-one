"""A B2B customer's trade profile, worked out (app/trade.py): credit status from
Finance's invoices, checked on every quote for Finance to confirm; the
products they carry from what they ordered; and the Priority / High priority
profile from their yearly contribution (GetMeds plus 2MG)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import finance, trade
from app.models import Deal, DealStage, FormField, Role, RolePermission, Team, User
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, sign_in
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids, line, save  # noqa: F401 (fixtures)


@pytest.fixture
def b2b(app, crew):  # noqa: F811 (a fixture)
    """North is B2B: the Credit terms and 2MG fields are on its form. Fin is Finance (confirms credit)."""
    with app.state.sessions() as db:
        north = db.scalar(select(Team).where(Team.name == "North"))
        db.add_all([
            FormField(entity="company", key="x_credit_terms", label="Credit terms", type="choice", options=["NET 30"], only_teams=[north.id], except_teams=[], only_types=[], except_types=[]),
            FormField(entity="company", key="x_2mg_sales", label="2MG sales, last 12 months", type="money", options=[], only_teams=[north.id], except_teams=[], only_types=[], except_types=[]),
        ])
        fin_role = Role(name="Finance", scope="all", grants=[RolePermission(permission=p) for p in ("quotes.view", "orders.credit", "customers.view")])
        db.add(fin_role)
        db.flush()
        db.add(User(email="fin@example.com", full_name="Fin Ance", password_hash=hash_password(PASSWORD), role_id=fin_role.id))
        db.commit()
    trade.forget_ranks()
    yield
    trade.forget_ranks()


def finance_answers(monkeypatch, rows: dict | None) -> None:
    monkeypatch.setattr(finance, "customer_standing", lambda settings, wanted: None if rows is None else {k: v for k, v in rows.items() if k in wanted})
    trade.forget_ranks()


def test_credit_status_from_what_finance_billed():
    assert trade.credit_of(None) == ("good", "Nothing owed.")
    assert trade.credit_of({"owedCentavos": 5000, "oldestDaysLate": 0, "approaching": True, "nextDueOn": "2026-10-20"})[0] == "approaching"
    assert trade.credit_of({"owedCentavos": 5000, "oldestDaysLate": 12})[0] == "overdue"
    assert trade.credit_of({"owedCentavos": 5000, "oldestDaysLate": 91})[0] == "suspended"
    assert trade.credit_of({"owedCentavos": 5000, "oldestDaysLate": 0, "approaching": False})[0] == "good"


def test_only_b2b_customers_have_a_trade_profile(client, crew, b2b, monkeypatch):  # noqa: F811
    finance_answers(monkeypatch, {})
    theirs = company(client, crew["ria"], "Mercury Pasig")  # North: B2B
    other = company(client, crew["sam"], "Corner clinic")  # South: not
    assert client.get(f"/companies/{theirs['id']}/trade", headers=crew["ria"]).json()["applies"] is True
    assert client.get(f"/companies/{other['id']}/trade", headers=crew["sam"]).json() == {"applies": False}


def test_profile_ranks_the_years_contribution_with_2mg(client, crew, b2b, monkeypatch):  # noqa: F811
    names = ["A", "B", "C", "D", "E"]
    made = {n: company(client, crew["ria"], f"Drugstore {n}") for n in names}
    billed = {"A": 900, "B": 700, "C": 500, "D": 300, "E": 0}
    finance_answers(monkeypatch, {made[n]["id"]: {"billedYearCentavos": v * 100_000, "owedCentavos": 0} for n, v in billed.items() if v})
    # E bought nothing from GetMeds but plenty from 2MG: 2MG counts.
    client.patch(f"/companies/{made['E']['id']}", json={"extra": {"x_2mg_sales": 1_000_000}}, headers=crew["ria"])  # pesos, as the form keeps it
    trade.forget_ranks()
    got = {n: client.get(f"/companies/{made[n]['id']}/trade", headers=crew["ria"]).json()["profile"] for n in names}
    assert got["E"]["level"] == "high" and got["E"]["twoMgCentavos"] == 100_000_000 and got["E"]["rank"] == 1
    assert got["A"]["level"] == "priority" and got["B"]["level"] == "priority"  # the next three tenths of 5 buyers: ranks 2-3
    assert got["D"]["level"] == "regular" and got["D"]["of"] == 5
    assert got["A"]["source"] == "finance"


def test_without_finance_the_profile_comes_from_won_deals(app, client, crew, b2b, monkeypatch):  # noqa: F811
    finance_answers(monkeypatch, None)
    acme = company(client, crew["ria"], "Acme Drug")
    with app.state.sessions() as db:
        won = db.scalar(select(DealStage).where(DealStage.outcome == "won"))
        owner = db.scalar(select(User).where(User.email == "ria@example.com"))
        db.add(Deal(name="Q4 supply", company_id=acme["id"], stage_code=won.code, probability=100, forecast_category="closed", value_centavos=250_000_00,
                    expected_close_on="2026-10-01", closed_at=datetime.now(UTC) - timedelta(days=10), owner_id=owner.id, team_id=owner.team_id))
        db.commit()
    trade.forget_ranks()
    got = client.get(f"/companies/{acme['id']}/trade", headers=crew["ria"]).json()
    assert got["profile"]["source"] == "deals" and got["profile"]["getmedsCentavos"] == 250_000_00
    assert got["credit"]["status"] is None and got["credit"]["label"] == "Not checked"  # Finance can't be asked
    assert got["financeLinked"] is False


def test_products_they_carry_come_from_finances_invoice_lines(client, crew, b2b, ids, monkeypatch):  # noqa: F811
    acme = company(client, crew["ria"], "Acme Drug")
    finance_answers(monkeypatch, {acme["id"]: {"owedCentavos": 0, "billedYearCentavos": 1, "lines": [
        {"ref": "AMX-500", "description": "Amoxicillin 500 mg", "invoices": 3, "lastOn": "2026-10-01"},
        {"ref": None, "description": "Freight", "invoices": 1, "lastOn": "2026-09-01"},
    ]}})
    carried = client.get(f"/companies/{acme['id']}/trade", headers=crew["ria"]).json()["carried"]
    assert carried[0]["code"] == "AMX-500" and carried[0]["id"] == ids["AMX-500"] and carried[0]["times"] == 3 and carried[0]["from"] == ["invoice"]
    assert carried[1]["id"] is None and carried[1]["name"] == "Freight"  # a line that isn't one of our products is still listed


def test_a_b2b_quote_is_credit_checked_and_finance_confirms_or_holds_it(app, client, crew, b2b, ids, monkeypatch):  # noqa: F811
    acme = company(client, crew["ria"], "Acme Drug")
    other = company(client, crew["sam"], "Corner clinic")
    finance_answers(monkeypatch, {acme["id"]: {"owedCentavos": 120_000_00, "overdueCentavos": 120_000_00, "oldestDaysLate": 40}})
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"])]).json()
    assert q["credit"]["status"] == "overdue" and q["credit"]["label"] == "Overdue" and q["credit"]["decision"] is None
    assert save(client, crew["sam"], other, [line(ids["AMX-500"])]).json()["credit"] is None  # not B2B: not checked

    fin = bearer(sign_in(client, "fin@example.com"))
    waiting = client.get("/quotes?task=credit", headers=fin).json()
    assert [x["id"] for x in waiting["items"]] == [q["id"]]  # Finance's list: the B2B quote only
    assert client.post(f"/quotes/{q['id']}/credit", json={"decision": "confirm"}, headers=crew["ria"]).status_code == 403  # Finance's call
    assert client.post(f"/quotes/{q['id']}/credit", json={"decision": "hold"}, headers=fin).status_code == 422  # a hold says why
    held = client.post(f"/quotes/{q['id']}/credit", json={"decision": "hold", "note": "Settle the August invoice first."}, headers=fin).json()
    assert held["credit"]["decision"] == "hold" and held["credit"]["byName"] == "Fin Ance" and held["can"]["order"] is False

    # Paid since: checked again, then confirmed.
    finance_answers(monkeypatch, {acme["id"]: {"owedCentavos": 0}})
    again = client.post(f"/quotes/{q['id']}/credit", json={"decision": "recheck"}, headers=fin).json()
    assert again["credit"]["status"] == "good" and again["credit"]["decision"] is None
    ok = client.post(f"/quotes/{q['id']}/credit", json={"decision": "confirm"}, headers=fin).json()
    assert ok["credit"]["decision"] == "confirmed"
    assert client.get("/quotes?task=credit", headers=fin).json()["total"] == 0  # decided: off the list
