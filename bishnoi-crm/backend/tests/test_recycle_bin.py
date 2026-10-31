"""Data clean-up and the recycle bin (2026-10-30, app/recycle_bin.py): an administrator deletes records to
the bin with what belongs only to them, restores them as they were, and erases them (30 days, or sooner)."""

from datetime import UTC, datetime, timedelta

from app.recycle_bin import BinEntry
from tests.test_customers import activity, company, contact


def test_only_administrators_clean_up(client, ana, ben):
    assert client.get("/data-cleanup/kinds", headers=ben).status_code == 403
    kinds = client.get("/data-cleanup/kinds", headers=ana).json()
    assert kinds["days"] == 30 and {"customers", "customer-types", "products", "quotes"} <= {k["key"] for k in kinds["kinds"]}
    assert not any(k["key"] in ("users", "roles", "teams") for k in kinds["kinds"])  # people are kept on the Platform


def test_a_customer_goes_to_the_bin_with_what_is_its_own_and_comes_back(client, ana):
    acme = company(client, ana, "Acme Test Clinic")
    maria = contact(client, ana, "Maria", companyId=acme["id"])
    call = activity(client, ana, companyId=acme["id"], contactId=maria["id"])
    found = client.get("/data-cleanup/kinds/customers", params={"q": "acme test"}, headers=ana).json()
    assert [i["label"] for i in found["items"]] == ["Acme Test Clinic"]
    r = client.post("/data-cleanup/kinds/customers/delete", json={"ids": [acme["id"]]}, headers=ana)
    assert r.status_code == 200, r.text
    assert client.get(f"/companies/{acme['id']}", headers=ana).status_code == 404
    # the contact and the call stay, no longer pointing at it
    assert client.get(f"/contacts/{maria['id']}", headers=ana).json()["company"] is None
    bin_ = client.get("/data-cleanup/bin", headers=ana).json()["items"]
    assert [b["label"] for b in bin_] == ["Acme Test Clinic"] and bin_[0]["kindName"] == "Customers"
    assert client.post(f"/data-cleanup/bin/{bin_[0]['id']}/restore", headers=ana).status_code == 200
    assert client.get(f"/companies/{acme['id']}", headers=ana).json()["name"] == "Acme Test Clinic"
    assert client.get(f"/contacts/{maria['id']}", headers=ana).json()["company"]["id"] == acme["id"]  # linked again
    assert any(i["id"] == call["id"] for i in client.get("/data-cleanup/kinds/activities", headers=ana).json()["items"])
    assert client.get("/data-cleanup/bin", headers=ana).json()["items"] == []


def test_something_still_used_refuses_and_says_what(client, ana):
    # a price type still on products' prices is taken with them (its own); a deal stage with deals refuses
    stages = client.get("/data-cleanup/kinds/deal-stages", headers=ana).json()["items"]
    acme = company(client, ana, "Acme Stage Test")
    deal = client.post("/deals", json={"name": "Big order", "companyId": acme["id"]}, headers=ana)
    assert deal.status_code == 201, deal.text
    used = deal.json()["stageCode"] if "stageCode" in deal.json() else deal.json()["stage"]["code"]
    r = client.post("/data-cleanup/kinds/deal-stages/delete", json={"ids": [used]}, headers=ana)
    assert r.status_code == 409 and "still used" in r.text and "deals" in r.text
    assert len(client.get("/data-cleanup/kinds/deal-stages", headers=ana).json()["items"]) == len(stages)


def test_erase_and_empty_and_thirty_days(app, client, ana):
    a, b = company(client, ana, "Erase Me One"), company(client, ana, "Erase Me Two")
    client.post("/data-cleanup/kinds/customers/delete", json={"ids": [a["id"], b["id"]]}, headers=ana)
    items = client.get("/data-cleanup/bin", headers=ana).json()["items"]
    assert len(items) == 2
    assert client.delete(f"/data-cleanup/bin/{items[0]['id']}", headers=ana).json() == {"erased": 1}
    # the last one ages past 30 days: erased the next time the bin is opened
    with app.state.sessions() as db:
        e = db.get(BinEntry, items[1]["id"])
        e.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert client.get("/data-cleanup/bin", headers=ana).json()["items"] == []
    c = company(client, ana, "Erase Me Three")
    client.post("/data-cleanup/kinds/customers/delete", json={"ids": [c["id"]]}, headers=ana)
    assert client.delete("/data-cleanup/bin", headers=ana).json() == {"erased": 1}


def test_a_set_up_list_keyed_by_code(client, ana):
    made = client.post("/admin/customer-types", json={"name": "Test Type Zeta"}, headers=ana)
    assert made.status_code == 201, made.text
    code = next(t["code"] for t in made.json() if t["name"] == "Test Type Zeta")
    r = client.post("/data-cleanup/kinds/customer-types/delete", json={"ids": [code]}, headers=ana)
    assert r.status_code == 200, r.text
    entry = client.get("/data-cleanup/bin", headers=ana).json()["items"][0]
    assert entry["label"] == "Test Type Zeta"
    assert client.post(f"/data-cleanup/bin/{entry['id']}/restore", headers=ana).status_code == 200
    assert any(i["id"] == code for i in client.get("/data-cleanup/kinds/customer-types", headers=ana).json()["items"])
