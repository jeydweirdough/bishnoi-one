"""The sidebar's red counts: what isn't set up yet, for whoever can fix it."""

from tests.conftest import make_company


def test_people_with_no_password_are_counted_for_admins(client, ana, ben):
    c = make_company(client, ana)
    person = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Jade", "email": "jade@x.test"}, headers=ana).json()["user"]
    before = client.get("/platform/unset", headers=ana).json().get("userPasswords", 0)
    assert before >= 1
    assert person["id"] in [u["id"] for u in client.get("/platform/users?password=none", headers=ana).json()["users"]]
    client.post(f"/platform/users/{person['id']}/password", json={}, headers=ana)
    assert client.get("/platform/unset", headers=ana).json().get("userPasswords", 0) == before - 1
    assert person["id"] not in [u["id"] for u in client.get("/platform/users?password=none", headers=ana).json()["users"]]
    # Support staff can't set passwords, so they aren't shown it.
    assert "userPasswords" not in client.get("/platform/unset", headers=ben).json()


def test_an_application_with_no_address(client, ana, ben):
    before = client.get("/platform/unset", headers=ben).json().get("applicationAddress", 0)
    r = client.post("/platform/applications", json={"key": "hr", "name": "HR"}, headers=ana)
    assert r.status_code == 201, r.text
    assert client.get("/platform/unset", headers=ben).json()["applicationAddress"] == before + 1
