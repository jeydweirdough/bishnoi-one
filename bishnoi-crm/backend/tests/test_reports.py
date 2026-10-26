"""The CRM's reports (app/routers/reports.py): each role gets the reports for the data it may see,
every figure narrowed to its reach, and every report answers in the report kit's shape."""

from app import finance
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)


def keys(client, headers) -> set[str]:
    return {r["key"] for r in client.get("/reports", headers=headers).json()}


def test_each_role_gets_the_reports_for_its_data(client, ana, crew):  # noqa: F811
    admin, rep = keys(client, ana), keys(client, crew["ria"])
    assert {"pipeline", "quotes", "new-customers", "activities", "scorecards"} <= admin
    assert "new-customers" in rep  # a salesperson sees reports, about their own work
    groups = {r["group"] for r in client.get("/reports", headers=ana).json()}
    assert {"Sales", "Customers", "Activities", "Field sales", "Performance", "Retention"} <= groups
    assert {"sales-attainment", "top-customers", "retention-trend", "customers-at-risk"} <= admin


def test_a_report_counts_only_what_the_person_reaches(client, crew):  # noqa: F811
    company(client, crew["ria"], "Ria Co")
    company(client, crew["rex"], "Rex Co")
    company(client, crew["sam"], "Sam Co")
    seen = lambda who: {r["customer"] for r in client.get("/reports/new-customers", headers=crew[who]).json()["rows"]}  # noqa: E731
    assert seen("ria") == {"Ria Co"}  # own
    assert seen("lia") == {"Ria Co", "Rex Co"}  # her team
    assert seen("max") == {"Ria Co", "Rex Co", "Sam Co"}  # everyone
    # A lead narrows to one of her people; someone out of her reach is ignored.
    body = client.get("/reports/new-customers", headers=crew["lia"]).json()
    rex = next(o["value"] for o in body["filters"][0]["options"] if o["label"] == "Rex")
    assert {r["customer"] for r in client.get(f"/reports/new-customers?owner={rex}", headers=crew["lia"]).json()["rows"]} == {"Rex Co"}
    # A salesperson has no person filter: only their own work.
    assert client.get("/reports/new-customers", headers=crew["ria"]).json()["filters"] == []


def test_every_report_answers_in_the_kits_shape(client, ana, monkeypatch):
    monkeypatch.setattr(finance, "sales_feed", lambda *a: None)
    company(client, ana, "Acme")
    for r in client.get("/reports", headers=ana).json():
        body = client.get(f"/reports/{r['key']}", headers=ana)
        assert body.status_code == 200, (r["key"], body.text)
        got = body.json()
        assert got["columns"] and isinstance(got["rows"], list) and isinstance(got["summary"], list), r["key"]
    assert client.get("/reports/nope", headers=ana).status_code == 404
    assert client.get("/reports/new-customers?from=2026-10-10&to=2026-10-01", headers=ana).status_code == 422
