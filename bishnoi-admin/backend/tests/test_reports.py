"""Executive Admin's reports (app/routers/reports.py): each needs the view permission for its data,
every report answers in the report kit's shape, and the Excel exports at /admin/reports/{kind} still work."""

from datetime import date, timedelta

from app.models import User
from app.permissions import ROLE_MARKETING_ID
from app.security import hash_password
from tests.test_rbac import PASSWORD, app, client, sign_in  # noqa: F401 (fixtures)


def soon(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def test_every_report_answers_and_renewals_look_ahead(client):
    admin, asst = sign_in(client), sign_in(client, "asst@example.com")
    assert client.post("/admin/vehicles", json={"name": "Ford Ranger AT", "plate": "NFY 4260", "registrationDue": soon(10), "pmsDue": soon(-3)}, headers=asst).status_code == 201
    listed = client.get("/admin/reports", headers=admin).json()
    assert {"Compliance", "Fleet and travel", "Service requests", "Marketing"} <= {r["group"] for r in listed}
    for r in listed:
        body = client.get(f"/admin/reports/{r['key']}", headers=admin)
        assert body.status_code == 200, (r["key"], body.text)
        assert body.json()["columns"], r["key"]
    dues = client.get("/admin/reports/vehicle-dues", headers=admin).json()
    assert [row["what"] for row in dues["rows"]] == ["Maintenance", "Registration"]  # overdue first, then the next 90 days
    assert dues["from"] == date.today().isoformat()
    assert client.get("/admin/reports/permits", headers=admin).status_code == 200  # the Excel export is still there


def test_a_role_sees_only_the_reports_for_its_data(app, client):
    with app.state.sessions() as db:
        db.add(User(email="mkt@example.com", full_name="Marketing", password_hash=hash_password(PASSWORD), role_id=ROLE_MARKETING_ID))
        db.commit()
    marketing = sign_in(client, "mkt@example.com")
    assert {r["group"] for r in client.get("/admin/reports", headers=marketing).json()} == {"Marketing"}
    assert client.get("/admin/reports/renewals-due", headers=marketing).status_code == 404
    assert client.get("/admin/reports/materials-stock", headers=marketing).status_code == 200
