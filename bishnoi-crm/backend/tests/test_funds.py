"""Marketing requests: asked for by a salesperson or field agent, decided by their
Team Lead, released and checked by Finance (here a stand-in answering as the
real one does), and liquidated receipt by receipt from the CRM."""

import pytest
from fastapi.testclient import TestClient

from app import funds
from app.config import Settings
from app.main import create_app
from app.models import Team, User
from app.routers.auth import attempts
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, fresh_database, role_id, sign_in

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class FakeFinance:
    """Finance's /integration/funds, as far as the CRM uses it."""

    def __init__(self):
        self.requests: dict[str, dict] = {}
        self.down = False
        self.sent: list[str] = []

    def release(self, source_id: str, amount: int | None = None):
        r = self.requests[source_id]
        r["release"] = {"amountCentavos": amount or r["approvedCentavos"], "method": "cash"}
        r["status"] = "to_liquidate" if r["liquidate"] else "closed"

    def __call__(self, settings, method, path, body=None, params=None, raw=False):
        if self.down:
            raise funds.FinanceUnavailable("Finance can't be reached right now.")
        parts = path.split("/")
        if path == "categories":
            return {"items": [{"id": "meals", "name": "Meals & representation", "reimbursable": True}]}
        if path == "requests" and method == "POST":
            self.sent.append(body["sourceId"])
            self.requests.setdefault(body["sourceId"], {**body, "status": "to_release", "expenses": []})
            return self.requests[body["sourceId"]]
        if path == "requests":
            return {"items": {i: self.requests[i] for i in params["ids"].split(",") if i in self.requests}}
        r = self.requests[parts[1]]
        if parts[2:] == ["expenses"]:
            if r["status"] != "to_liquidate":
                raise funds.FinanceRefused("It's with Finance now, so that can't be done.", 409)
            r["expenses"].append({"id": f"e{len(r['expenses']) + 1}", "amountCentavos": body["amountCentavos"], "receipt": {"name": body["receipt"]["name"]} if "receipt" in body else None})
        elif parts[2:] == ["submit"]:
            r["status"] = "to_check"
        elif parts[2:] == ["cancel"]:
            if r["status"] != "to_release":
                raise funds.FinanceRefused("It's released now, so that can't be done.", 409)
            r["status"] = "cancelled"
        elif parts[2] == "expenses" and raw:
            return PNG, "image/png"
        return r


@pytest.fixture
def finance(monkeypatch):
    fake = FakeFinance()
    monkeypatch.setattr(funds, "call", fake)
    return fake


@pytest.fixture
def app(tmp_path, finance):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), files_dir=tmp_path / "files",
                        finance_api_url="http://finance.test", finance_api_key="k" * 32)
    app = create_app(settings)
    with app.state.sessions() as db:
        north, south = Team(name="North"), Team(name="South")
        db.add_all([north, south])
        db.flush()
        people = {"ana": ("Administrator", None), "rico": ("Salesperson", north.id), "fay": ("Field agent", north.id),
                  "tess": ("Team Lead", north.id), "sol": ("Salesperson", south.id), "lee": ("Team Lead", south.id)}
        for name, (role, team) in people.items():
            db.add(User(email=f"{name}@example.com", full_name=name.title(), password_hash=hash_password(PASSWORD), role_id=role_id(db, role), team_id=team))
        db.commit()
    yield app
    app.state.sessions.kw["bind"].dispose()


@pytest.fixture
def who(client: TestClient) -> dict[str, dict]:
    return {n: bearer(sign_in(client, f"{n}@example.com")) for n in ("ana", "rico", "fay", "tess", "sol", "lee")}


def purposes(client, headers) -> dict[str, dict]:
    return {p["name"]: p for p in client.get("/funds/purposes", headers=headers).json()["items"]}


def ask(client, headers, amount=500000, purpose="Partnership dinner / client meal") -> dict:
    body = {"purposeId": purposes(client, headers)[purpose]["id"], "amountCentavos": amount, "details": "Dinner with Dr. Reyes and staff"}
    r = client.post("/funds", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_salespeople_and_agents_ask_and_their_lead_is_told(client, who):
    mine = ask(client, who["rico"])
    assert mine["number"].startswith("FR-") and mine["status"] == "pending" and mine["liquidate"] is True
    ask(client, who["fay"], purpose="Transportation & travel")
    assert client.get("/funds/waiting", headers=who["tess"]).json()["toApprove"] == 2
    # Another team's lead isn't asked, and a salesperson approves nothing.
    assert client.get("/funds/waiting", headers=who["lee"]).json()["toApprove"] == 0
    assert client.get("/funds?show=approve", headers=who["rico"]).json()["items"] == []
    assert client.get(f"/funds/{mine['id']}", headers=who["sol"]).status_code == 404


def test_approved_goes_to_finance_and_follows_it(client, who, finance):
    r = ask(client, who["rico"])
    assert client.post(f"/funds/{r['id']}/approve", json={}, headers=who["rico"]).status_code == 403  # not their own
    done = client.post(f"/funds/{r['id']}/approve", json={"approvedCentavos": 400000, "note": "Keep it to four"}, headers=who["tess"]).json()
    assert done["status"] == "to_release" and done["approvedCentavos"] == 400000
    assert finance.requests[r["id"]]["approvedByName"] == "Tess" and finance.requests[r["id"]]["requesterEmail"] == "rico@example.com"
    finance.release(r["id"])
    seen = client.get(f"/funds/{r['id']}", headers=who["rico"]).json()
    assert seen["status"] == "to_liquidate" and seen["can"]["liquidate"]
    assert client.get("/funds/waiting", headers=who["rico"]).json()["toLiquidate"] == 1


def test_liquidated_receipt_by_receipt(client, who, finance):
    r = ask(client, who["rico"])
    client.post(f"/funds/{r['id']}/approve", json={}, headers=who["tess"])
    # Not before the money's released.
    early = client.post(f"/funds/{r['id']}/expenses", data={"spentOn": "2026-09-20", "description": "Dinner", "categoryId": "meals", "amountCentavos": "320000"},
                        files={"receipt": ("receipt.png", PNG, "image/png")}, headers=who["rico"])
    assert early.status_code == 409
    finance.release(r["id"])
    form = {"spentOn": "2026-09-20", "description": "Dinner", "categoryId": "meals", "amountCentavos": "320000"}
    assert client.post(f"/funds/{r['id']}/expenses", data=form, headers=who["rico"]).status_code == 422  # a receipt, or why not
    assert client.post(f"/funds/{r['id']}/expenses", data=form, files={"receipt": ("x.txt", b"hello", "text/plain")}, headers=who["rico"]).status_code == 422
    added = client.post(f"/funds/{r['id']}/expenses", data=form, files={"receipt": ("receipt.png", PNG, "image/png")}, headers=who["rico"])
    assert added.status_code == 201, added.text
    added = added.json()
    assert added["finance"]["expenses"][0]["amountCentavos"] == 320000
    # Only the requester liquidates; their lead can see the receipt.
    assert client.post(f"/funds/{r['id']}/submit", headers=who["tess"]).status_code == 403
    assert client.get(f"/funds/{r['id']}/expenses/e1/receipt", headers=who["tess"]).content == PNG
    sent = client.post(f"/funds/{r['id']}/submit", headers=who["rico"]).json()
    assert sent["status"] == "to_check" and sent["statusLabel"] == "Liquidation under review"


def test_declined_and_cancelled(client, who, finance):
    a, b, c = ask(client, who["rico"]), ask(client, who["rico"]), ask(client, who["rico"])
    assert client.post(f"/funds/{a['id']}/decline", json={}, headers=who["tess"]).status_code == 422  # say why
    assert client.post(f"/funds/{a['id']}/decline", json={"note": "Next month"}, headers=who["tess"]).json()["status"] == "declined"
    assert client.post(f"/funds/{b['id']}/cancel", json={}, headers=who["rico"]).json()["status"] == "cancelled"
    client.post(f"/funds/{c['id']}/approve", json={}, headers=who["tess"])
    assert client.post(f"/funds/{c['id']}/cancel", json={"reason": "Moved"}, headers=who["rico"]).json()["status"] == "cancelled"
    assert finance.requests[c["id"]]["status"] == "cancelled"


def test_finance_down_never_loses_an_approval(client, who, finance):
    r = ask(client, who["rico"])
    finance.down = True
    done = client.post(f"/funds/{r['id']}/approve", json={}, headers=who["tess"]).json()
    assert done["status"] == "approved" and "can't be reached" in done["financeError"]
    finance.down = False
    # Sent the next time anyone looks.
    assert client.get(f"/funds/{r['id']}", headers=who["rico"]).json()["status"] == "to_release"
    assert finance.sent == [r["id"]]


def test_the_purpose_decides_liquidation_and_the_lead_can_change_it(client, who, finance):
    allowance = ask(client, who["fay"], amount=100000, purpose="Allowance")
    assert allowance["liquidate"] is False
    r = ask(client, who["fay"])
    done = client.post(f"/funds/{r['id']}/approve", json={"liquidate": False}, headers=who["tess"]).json()
    assert done["liquidate"] is False and finance.requests[r["id"]]["liquidate"] is False


def test_purposes_are_the_admins(client, who):
    assert client.post("/admin/fund-purposes", json={"name": "Seminar"}, headers=who["tess"]).status_code == 403
    made = client.post("/admin/fund-purposes", json={"name": "Seminar", "liquidate": False}, headers=who["ana"])
    assert made.status_code == 201
    client.put(f"/admin/fund-purposes/{made.json()['id']}", json={"name": "Seminar", "isActive": False}, headers=who["ana"])
    assert "Seminar" not in purposes(client, who["rico"])
