"""Each staff account, user, company and application has a number from
40000001 up, beside its id (app/numbering.py, migration 0007)."""

from tests.conftest import make_company


def test_records_are_numbered_from_40000001(client, ana):
    staff = client.get("/platform/staff", headers=ana).json()["staff"]
    assert sorted(s["no"] for s in staff) == [40000001, 40000002]  # Ana and Ben, as they were made
    assert client.get("/auth/me", headers=ana).json()["user"]["no"] in (40000001, 40000002)
    first = make_company(client, ana, name="GetMeds")
    second = make_company(client, ana, name="Northwind")
    assert (first["no"], second["no"]) == (40000001, 40000002)  # each table counts on its own
    person = client.post("/platform/users", json={"companyId": first["id"], "fullName": "Paolo", "email": "p@x.test"}, headers=ana).json()["user"]
    assert person["no"] == 40000001
    assert all(a["no"] >= 40000001 for a in client.get("/platform/applications", headers=ana).json()["applications"])
