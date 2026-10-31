"""Connected to Bishnoi One, the CRM's settings are changed only by the company's administrators (2026-10-31):
a role that holds a settings permission may still read, but its changes are refused. Standalone, as before
(tests/test_customers.py)."""

from app.models import RolePermission
from tests.conftest import role_id
from tests.test_company import platform  # noqa: F401 (fixture: a stand-in Platform)


def test_connected_only_the_administrator_changes_a_setting(app, client, ana, ben, platform):  # noqa: F811
    with app.state.sessions() as db:
        db.add(RolePermission(role_id=role_id(db, "Salesperson"), permission="admin.types"))
        db.commit()
    # Ben's role holds the permission, but connected only an administrator changes settings.
    refused = client.post("/admin/customer-types", json={"name": "Wholesaler"}, headers=ben)
    assert refused.status_code == 403 and "administrators" in refused.json()["detail"]
    assert client.get("/customer-types", headers=ben).status_code == 200  # reading is never limited
    assert client.post("/admin/customer-types", json={"name": "Wholesaler"}, headers=ana).status_code == 201
    # Monthly targets stay with whoever may set goals: not a setting.
    assert "administrators" not in client.put("/kpi-targets", json={}, headers=ben).text
