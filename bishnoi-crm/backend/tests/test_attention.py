"""The home page's prompts (app/attention.py): what needs someone's attention,
most pressing first; put aside for a week or for good; rules per division."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models import Company, Quote, User
from tests.test_customers import activity, company, crew  # noqa: F401 (crew is a fixture)


def kinds(client, headers) -> list[str]:
    return [p["kind"] for p in client.get("/attention", headers=headers).json()]


def by_kind(client, headers, kind: str) -> list[dict]:
    return [p for p in client.get("/attention", headers=headers).json() if p["kind"] == kind]


def test_an_overdue_follow_up_comes_first(client, crew):
    acme = company(client, crew["ria"])
    past = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    activity(client, crew["ria"], kind="task", subject="Send the price list", companyId=acme["id"], at=past)
    first = client.get("/attention", headers=crew["ria"]).json()[0]
    assert (first["kind"], first["title"], first["reason"]) == ("overdue", "Send the price list with Acme", "3 days overdue.")
    assert by_kind(client, crew["rex"], "overdue") == []  # only the person who can act


def test_a_birthday_coming_up(app, client, crew):
    acme = company(client, crew["ria"], "Dr. Santos")
    soon = date.today() + timedelta(days=3)
    with app.state.sessions() as db:
        c = db.get(Company, acme["id"])
        c.extra = {"x_birth_date": f"1975-{soon:%m-%d}"}
        db.commit()
    [p] = by_kind(client, crew["ria"], "occasion")
    assert p["title"] == "Dr. Santos's birthday is in 3 days" and p["href"] == f"/companies/{acme['id']}"


def test_quiet_customers_and_putting_a_prompt_aside(app, client, crew):
    acme = company(client, crew["ria"])
    with app.state.sessions() as db:
        db.get(Company, acme["id"]).created_at = datetime.now(UTC) - timedelta(days=50)
        db.commit()
    [quiet] = by_kind(client, crew["ria"], "quiet")
    assert "50 days" in quiet["title"]
    assert client.post("/attention/put-aside", json={"key": quiet["key"], "how": "snooze"}, headers=crew["ria"]).status_code == 204
    assert by_kind(client, crew["ria"], "quiet") == []
    # The rules are an administrator's to set.
    assert client.put("/admin/attention-rules", json={"quietDays": 90, "noticeDays": 7, "clidpDays": 30, "stuckDays": 2}, headers=crew["ria"]).status_code == 403


def test_rules_per_division(client, ana, crew):
    rules = client.get("/admin/attention-rules", headers=ana).json()
    assert rules["everyone"]["quietDays"] == 45 and rules["divisions"] == []
    north = next(t for t in rules["teams"] if t["name"] == "North")
    saved = client.put("/admin/attention-rules", json={"teamId": north["id"], "quietDays": 90, "noticeDays": 14, "clidpDays": 30, "stuckDays": 2}, headers=ana).json()
    assert [(d["team"]["name"], d["quietDays"]) for d in saved["divisions"]] == [("North", 90)]
    assert client.delete(f"/admin/attention-rules/{north['id']}", headers=ana).json()["divisions"] == []


def test_a_quote_waiting_too_long(app, client, crew):
    with app.state.sessions() as db:
        ria = db.scalar(select(User).where(User.email == "ria@example.com"))
        db.add(Quote(number="Q-1", owner_id=ria.id, team_id=ria.team_id, approval_status="pending", created_at=datetime.now(UTC) - timedelta(days=5),
                     customer_name="Acme", price_type="PATIENT", price_type_name="Patient", lines=[], gross_centavos=0, discount_centavos=0, total_centavos=0))
        db.commit()
    assert [p["title"] for p in by_kind(client, crew["ria"], "quote")] == ["Quote Q-1 is still waiting for approval"]
    assert [p["title"] for p in by_kind(client, crew["lia"], "quote")] == ["Quote Q-1 is waiting for your approval"]  # her team lead


def test_a_call_planned_with_its_objective_and_products(app, client, crew):
    with app.state.sessions() as db:
        from app.models import Product

        db.add_all([Product(code="ONC-1", name="Onco One"), Product(code="ONC-2", name="Onco Two")])
        db.commit()
    acme = company(client, crew["ria"])
    soon = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    call = activity(client, crew["ria"], kind="meeting", subject="Introduce Onco One", companyId=acme["id"], at=soon, objective="Get Onco One on their formulary", products=["ONC-1", "ONC-2"])
    assert call["objective"] == "Get Onco One on their formulary" and [p["name"] for p in call["products"]] == ["Onco One", "Onco Two"]
    assert client.post("/activities", json={"kind": "meeting", "subject": "x", "products": ["NOPE"]}, headers=crew["ria"]).status_code == 422
    # Afterwards: what came of it, and what was actually discussed.
    done = client.patch(f"/activities/{call['id']}", json={"done": True, "outcome": "Interested; wants samples", "discussed": ["ONC-1"]}, headers=crew["ria"]).json()
    assert done["isDone"] and done["outcome"] == "Interested; wants samples" and [p["code"] for p in done["discussed"]] == ["ONC-1"]
