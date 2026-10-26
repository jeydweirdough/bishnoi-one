"""Tests for saved reports on the Platform (app/routers/saved_reports.py).
Each report's choices are stored on the Platform; they are scoped to company and app.
"""

import pytest
from tests.conftest import app_id, make_company


def auth_header(client, email, password):
    r = client.post("/identity/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.fixture
def people(client, ana):
    c = make_company(client, ana, name="Test Company", apps=("crm", "finance"))
    # Person 1: Jade (Salesperson)
    u1 = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Jade Madrigal", "email": "jade@company.test"}, headers=ana).json()["user"]
    p1 = client.post(f"/platform/users/{u1['id']}/password", json={"password": "Password123!"}, headers=ana)
    # Person 2: Roy (Salesperson in same company)
    u2 = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Roy Rivera", "email": "roy@company.test"}, headers=ana).json()["user"]
    p2 = client.post(f"/platform/users/{u2['id']}/password", json={"password": "Password123!"}, headers=ana)
    # Company admin
    admin = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Admin User", "email": "admin@company.test", "isCompanyAdmin": True}, headers=ana).json()["user"]
    client.post(f"/platform/users/{admin['id']}/password", json={"password": "Password123!"}, headers=ana)

    # Another company
    c2 = make_company(client, ana, name="Other Company", apps=("crm",))
    u3 = client.post("/platform/users", json={"companyId": c2["id"], "fullName": "Other User", "email": "other@other.test"}, headers=ana).json()["user"]
    client.post(f"/platform/users/{u3['id']}/password", json={"password": "Password123!"}, headers=ana)

    return {
        "jade": auth_header(client, "jade@company.test", "Password123!"),
        "roy": auth_header(client, "roy@company.test", "Password123!"),
        "admin": auth_header(client, "admin@company.test", "Password123!"),
        "other": auth_header(client, "other@other.test", "Password123!"),
    }


def test_saved_report_lifecycle(client, people):
    jade = people["jade"]
    roy = people["roy"]
    admin = people["admin"]
    other = people["other"]

    # 1. Jade saves a private custom report
    def1 = {
        "columns": ["customer", "total"],
        "filters": [{"column": "total", "op": "gt", "value": "1000"}],
        "groupBy": "customer",
        "sort": [{"column": "total", "desc": True}],
        "chart": "bar",
    }
    r = client.post(
        "/identity/reports",
        json={"app": "crm", "baseKey": "sales-by-customer", "name": "Top Customers > 1k", "definition": def1, "shared": False},
        headers=jade,
    )
    assert r.status_code == 201
    saved = r.json()
    assert saved["name"] == "Top Customers > 1k"
    assert saved["baseKey"] == "sales-by-customer"
    assert saved["shared"] is False
    assert saved["mine"] is True
    report_id = saved["id"]

    # Jade lists crm reports: sees her report
    list_jade = client.get("/identity/reports?app=crm", headers=jade).json()
    assert len(list_jade) == 1
    assert list_jade[0]["id"] == report_id

    # Roy lists crm reports: does NOT see Jade's private report
    list_roy = client.get("/identity/reports?app=crm", headers=roy).json()
    assert len(list_roy) == 0

    # Roy tries to read Jade's private report: 404
    assert client.get(f"/identity/reports/{report_id}", headers=roy).status_code == 404

    # Other company tries to read: 404
    assert client.get(f"/identity/reports/{report_id}", headers=other).status_code == 404

    # 2. Jade shares the report with the company
    patch_r = client.patch(f"/identity/reports/{report_id}", json={"shared": True}, headers=jade)
    assert patch_r.status_code == 200
    assert patch_r.json()["shared"] is True

    # Now Roy sees it
    list_roy2 = client.get("/identity/reports?app=crm", headers=roy).json()
    assert len(list_roy2) == 1
    assert list_roy2[0]["id"] == report_id
    assert list_roy2[0]["mine"] is False
    assert list_roy2[0]["owner"] == "Jade Madrigal"

    # Roy cannot edit Jade's report
    assert client.patch(f"/identity/reports/{report_id}", json={"name": "Hacked"}, headers=roy).status_code == 404

    # Roy cannot delete Jade's report
    assert client.delete(f"/identity/reports/{report_id}", headers=roy).status_code == 404

    # 3. Company Admin can delete shared reports
    del_r = client.delete(f"/identity/reports/{report_id}", headers=admin)
    assert del_r.status_code == 204

    # Confirm it is gone
    assert client.get(f"/identity/reports/{report_id}", headers=jade).status_code == 404
