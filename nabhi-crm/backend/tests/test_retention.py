"""Retention: kept, lost, at risk, and who sees whose."""

from datetime import UTC, datetime, timedelta

from app.models import Company, Quote
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)


def quoted(app, company_id: str, days_ago: int, rejected: bool = False) -> None:
    with app.state.sessions() as db:
        c = db.get(Company, company_id)
        n = db.query(Quote).count() + 1
        db.add(
            Quote(
                number=f"Q-T-{n:04d}", company_id=c.id, customer_name=c.name, price_type="X", price_type_name="X", lines=[],
                approval_status="rejected" if rejected else "none", owner_id=c.owner_id, team_id=c.team_id,
                created_at=datetime.now(UTC) - timedelta(days=days_ago, hours=1),
            )
        )
        db.commit()


def test_figures_and_the_watch_list(app, client, crew):
    kept = company(client, crew["ria"], "Kept")  # quoted before, and again lately
    quoted(app, kept["id"], 120)
    quoted(app, kept["id"], 10)
    gone = company(client, crew["ria"], "Gone")  # quoted before, not since
    quoted(app, gone["id"], 100)
    risky = company(client, crew["ria"], "Risky")  # quiet 70 days: at risk
    quoted(app, risky["id"], 70)
    company(client, crew["ria"], "Never")
    rejected = company(client, crew["ria"], "Rejected")
    quoted(app, rejected["id"], 5, rejected=True)  # doesn't count

    r = client.get("/retention", headers=crew["ria"])
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert (s["base"], s["retained"], s["lost"], s["rate"]) == (2, 1, 1, 0.5)
    assert (s["customers"], s["healthy"], s["atRisk"], s["lostNow"], s["noQuotes"]) == (5, 1, 1, 1, 2)
    watch = [w["name"] for w in r.json()["watch"]]
    assert watch == ["Risky", "Gone"]  # at risk first, then lost lately
    assert len(r.json()["trend"]) == 6


def test_who_sees_what(app, client, crew):
    company(client, crew["ria"], "Ria Co")
    company(client, crew["sam"], "Sam Co")
    assert client.get("/retention?view=team", headers=crew["ria"]).status_code == 403  # reps: their own
    lead = client.get("/retention?view=team", headers=crew["lia"]).json()
    assert lead["summary"]["customers"] == 1 and [r["name"] for r in lead["reps"]] == ["Ria"]
    assert client.get("/retention?view=team", headers=crew["max"]).json()["summary"]["customers"] == 2
    csv = client.get("/retention/export?view=team", headers=crew["max"])
    assert csv.status_code == 200 and "Sam Co" in csv.text and csv.headers["content-type"].startswith("text/csv")
    team_csv = client.get("/retention/export?view=team", headers=crew["lia"])  # a lead exports their own team
    assert team_csv.status_code == 200 and "Ria Co" in team_csv.text and "Sam Co" not in team_csv.text
