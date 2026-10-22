"""The Overview's dashboard (planned 2026-10-22): each role gets the sections
its work calls for, judged by what it may do; the starting roles keep the
Overview as it was; the CRM's waiting prices are asked on their own and kept a
minute."""

from datetime import date, timedelta

import pytest

from app.crm import CrmUnavailable
from app.routers import finance

from .test_auth import PASSWORD, bearer, sign_in
from .test_funds import KEY, approved, categories, check_all, release, spend
from .test_invoices import issued, ready
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

VIEW = ["dashboard.view", "funds.view", "categories.view", "invoices.view", "journal.view", "accounts.view", "tax.view", "prices.view"]
# As planned for Ms. Malou and Sir Rommel (Plans/Plan - Finance accounts, 2026-10-20).
HEAD = VIEW + ["funds.check", "funds.cancel", "categories.manage", "invoices.create", "invoices.issue", "invoices.collect",
               "invoices.void", "invoices.setup", "journal.post", "journal.reverse", "accounts.manage", "tax.manage",
               "prices.approve", "admin.audit"]
BIR = VIEW + ["journal.post", "accounts.manage", "tax.manage", "admin.audit"]
# Ms. Cristal: the Head's, but releasing and settling instead of reviewing (Malou Q11).
DEPUTY = [p for p in HEAD if p != "funds.check"] + ["funds.release", "funds.settle"]


def person(client, ana, name: str, permissions: list[str]) -> dict:
    """A role with these permissions, someone in it, signed in."""
    role = client.post("/admin/roles", json={"name": name, "permissions": permissions}, headers=ana)
    assert role.status_code == 201, role.text
    email = f"{name.lower().replace(' ', '.')}@example.com"
    made = client.post("/admin/users", json={"email": email, "fullName": name, "roleId": role.json()["id"], "password": PASSWORD}, headers=ana)
    assert made.status_code == 201, made.text
    return bearer(sign_in(client, email))


@pytest.fixture
def malou(client, ana):
    return person(client, ana, "Finance Head", HEAD)


@pytest.fixture
def rommel(client, ana):
    return person(client, ana, "BIR and Compliance", BIR)


@pytest.fixture
def cristal(client, ana):
    return person(client, ana, "Finance Deputy", DEPUTY)


@pytest.fixture(autouse=True)
def nothing_kept():
    finance.forget_waiting_prices()
    yield
    finance.forget_waiting_prices()


def keys(client, who) -> list[str]:
    return [s["key"] for s in client.get("/finance/dashboard", headers=who).json()["sections"]]


def section(client, who, key: str) -> dict:
    return next(s for s in client.get("/finance/dashboard", headers=who).json()["sections"] if s["key"] == key)


def test_the_starting_roles_keep_the_overview(client, ana, ben):
    for who in (ana, ben):
        assert client.get("/finance/dashboard", headers=who).json() == {"kept": True, "sections": []}


def test_each_role_gets_the_sections_its_work_calls_for(client, malou, rommel, cristal):
    assert keys(client, malou) == ["waiting", "receivables", "sales", "spending", "journal", "tax", "cash"]
    assert keys(client, rommel) == ["journal", "tax", "cash"]
    assert keys(client, cristal) == ["waiting", "receivables", "sales", "spending", "journal", "tax", "cash"]


def test_the_deputy_waits_on_releases_and_settlements(client, malou, cristal):
    req = approved(client)
    waiting = section(client, cristal, "waiting")
    assert (waiting["canRelease"], waiting["canSettle"], waiting["canReview"]) == (True, True, False)
    assert waiting["toRelease"] == 1 and waiting["toSettle"] == 0
    # The head reviews, so she isn't asked to release or settle.
    head = section(client, malou, "waiting")
    assert (head["canRelease"], head["canSettle"], head["canReview"]) == (False, False, True)

    release(client, cristal, req["id"])
    spend(client, 320000, categories(client)["Food"])
    sent = client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico Santos"}, headers=KEY).json()
    assert check_all(client, malou, sent)["status"] == "to_return"  # less was spent: the rest comes back
    waiting = section(client, cristal, "waiting")
    assert waiting["toRelease"] == 0 and waiting["toSettle"] == 1


def test_waiting_counts_reviews_but_not_ones_you_released(client, ana, ben, malou):
    # A role that both releases and reviews (Finance Staff is a starting role, so make one).
    both = person(client, ana, "Release and review", VIEW + ["funds.release", "funds.check"])
    mine = release(client, both, approved(client)["id"])
    client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY)
    theirs = release(client, ben, approved(client, "req-2", requester=("Lia Cruz", "lia@example.com"))["id"])
    client.post("/integration/funds/requests/req-2/submit", json={"by": "Lia"}, headers=KEY)
    assert mine["id"] != theirs["id"]
    # Two wait for review: Malou may review both; the one who released req-1 only req-2.
    assert section(client, malou, "waiting")["toReview"] == 2
    assert section(client, both, "waiting")["toReview"] == 1


def test_overdue_liquidations_are_counted(app, client, ben, malou):
    from app.models import FundRequest

    r = release(client, ben, approved(client)["id"])
    with app.state.sessions() as db:
        db.get(FundRequest, r["id"]).liquidate_by = date.today() - timedelta(days=3)
        db.commit()
    assert section(client, malou, "waiting")["overdueLiquidations"] == 1


def test_receivables_sales_and_the_quarters_tax(client, ana, malou, rommel):
    ready(client, ana)
    today_inv = issued(client, ana)
    late = issued(client, ana, customerName="Watsons BGC", invoiceDate=(date.today() - timedelta(days=75)).isoformat(), termsDays=30)
    ar = section(client, malou, "receivables")
    assert ar["totalCentavos"] == today_inv["totalCentavos"] + late["totalCentavos"] and ar["customers"] == 2
    assert [c["name"] for c in ar["mostOverdue"]] == ["Watsons BGC"]  # only the late one
    sales = section(client, malou, "sales")
    assert sales["month"] == {"count": 1, "totalCentavos": today_inv["totalCentavos"], "taxCentavos": today_inv["taxCentavos"]}
    tax = section(client, rommel, "tax")
    assert tax["quarterTaxCentavos"] >= today_inv["taxCentavos"] > 0
    assert tax["quarter"].startswith("Q")


def test_spending_by_team_counts_accepted_covered_receipts(client, ana, ben, malou):
    req = release(client, ben, approved(client)["id"])
    cats = categories(client)
    spend(client, 320000, cats["Food"])
    spend(client, 50000, cats["Personal"], receipt=False)  # the person's own: not the company's spending
    sent = client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY).json()
    for e in sent["expenses"]:
        client.patch(f"/finance/funds/{req['id']}/expenses/{e['id']}", json={"accepted": True}, headers=ana)
    client.post(f"/finance/funds/{req['id']}/finish-check", headers=ana)
    teams = section(client, malou, "spending")["teams"]
    assert teams == [{"team": "North Luzon", "yearCentavos": 320000, "monthCentavos": 320000}]


def test_journal_shows_the_latest_and_who_posted_them(client, ana, rommel):
    accounts = {a["code"]: a for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]}
    body = {"date": date.today().isoformat(), "memo": "Bank charges", "lines": [
        {"accountId": accounts["6900"]["id"] if "6900" in accounts else accounts["6100"]["id"], "debitCentavos": 5000},
        {"accountId": accounts["1010"]["id"], "creditCentavos": 5000},
    ]}
    posted = client.post("/finance/ledger/entries", json=body, headers=rommel)
    assert posted.status_code == 201, posted.text
    journal = section(client, rommel, "journal")
    assert journal["latest"][0]["memo"] == "Bank charges" and journal["latest"][0]["postedBy"] == "BIR and Compliance"
    # Typed by hand, it waits for approval: shown on his side, not counted yet.
    assert journal["latest"][0]["status"] == "waiting" and journal["myWaiting"] == 1 and journal["thisMonth"] == 0
    assert client.post(f"/finance/ledger/entries/{posted.json()['id']}/approve", headers=ana).status_code == 200
    journal = section(client, rommel, "journal")
    assert journal["balanced"] is True and journal["thisMonth"] == 1 and journal["myWaiting"] == 0


def test_waiting_prices_are_kept_a_minute_and_a_failure_is_not(client, malou, rommel, monkeypatch):
    asked = []

    def crm(settings):
        asked.append(1)
        return {"prices": [{"productId": "p1"}], "quotes": [{"id": "q1"}, {"id": "q2"}], "total": 3}

    monkeypatch.setattr(finance, "waiting_prices", crm)
    assert client.get("/finance/dashboard/waiting-prices", headers=malou).json() == {"available": True, "prices": 1, "quotes": 2}
    client.get("/finance/dashboard/waiting-prices", headers=malou)
    assert len(asked) == 1  # the second visit used the kept answer
    # Only someone who approves prices asks.
    assert client.get("/finance/dashboard/waiting-prices", headers=rommel).status_code == 403

    finance.forget_waiting_prices()

    def down(settings):
        raise CrmUnavailable("The CRM can't be reached just now. Try again in a minute.")

    monkeypatch.setattr(finance, "waiting_prices", down)
    assert client.get("/finance/dashboard/waiting-prices", headers=malou).json() == {
        "available": False, "message": "The CRM can't be reached just now. Try again in a minute.",
    }
    monkeypatch.setattr(finance, "waiting_prices", crm)
    assert client.get("/finance/dashboard/waiting-prices", headers=malou).json()["available"] is True  # the failure wasn't kept
