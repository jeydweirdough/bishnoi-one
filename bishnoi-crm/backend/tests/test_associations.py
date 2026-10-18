"""Associations (P13): records linked with a label, read from both sides; one
activity on several customers."""

from tests.test_customers import activity, company, contact, crew  # noqa: F401 (crew is a fixture)
from tests.test_deals import deal


def groups(client, headers, kind, rid) -> dict[str, list[str]]:
    body = client.get(f"/associations?type={kind}&id={rid}", headers=headers).json()
    return {g["name"]: [i["name"] for i in g["items"]] for g in body["groups"]}


def link(client, headers, label, side, kind, rid, other):
    return client.post("/associations", json={"label": label, "side": side, "type": kind, "id": rid, "otherId": other}, headers=headers)


def test_a_doctor_works_at_a_hospital_read_both_ways(client, crew):
    doctor = company(client, crew["ria"], "Dr. Reyes")
    hospital = company(client, crew["sam"], "Manila Cancer Center")  # another team's
    assert [t["name"] for t in client.get("/associations/targets?type=company&q=cancer", headers=crew["ria"]).json()] == ["Manila Cancer Center"]
    assert link(client, crew["ria"], "works_at", "from", "company", doctor["id"], hospital["id"]).status_code == 201
    assert groups(client, crew["ria"], "company", doctor["id"]) == {"Works at": ["Manila Cancer Center"]}
    # From the hospital: the doctor is there, under the other side's name.
    assert groups(client, crew["sam"], "company", hospital["id"]) == {"People here": ["Dr. Reyes"]}
    mine = client.get(f"/associations?type=company&id={doctor['id']}", headers=crew["ria"]).json()
    item = mine["groups"][0]["items"][0]
    assert item["canOpen"] is False  # Sam's: named, not opened
    # Linking twice is once; a label from the wrong side is refused.
    assert link(client, crew["ria"], "works_at", "from", "company", doctor["id"], hospital["id"]).json()["id"] == item["associationId"]
    assert link(client, crew["ria"], "decision_maker", "from", "company", doctor["id"], hospital["id"]).status_code == 422
    assert client.delete(f"/associations/{item['associationId']}", headers=crew["ria"]).status_code == 204
    assert groups(client, crew["ria"], "company", doctor["id"]) == {}


def test_a_decision_maker_on_a_deal(client, crew):
    acme = company(client, crew["ria"])
    maria = contact(client, crew["ria"], companyId=acme["id"])
    d = deal(client, crew["ria"], acme)
    assert link(client, crew["ria"], "decision_maker", "to", "deal", d["id"], maria["id"]).status_code == 201
    assert groups(client, crew["ria"], "deal", d["id"]) == {"Decision makers": ["Maria"]}
    assert groups(client, crew["ria"], "contact", maria["id"]) == {"Decision maker on": ["Q4 order"]}
    # Someone else's deal or contact can't be linked.
    other = company(client, crew["sam"], "Beta")
    theirs = deal(client, crew["sam"], other)
    assert link(client, crew["ria"], "decision_maker", "from", "contact", maria["id"], theirs["id"]).status_code == 422


def test_one_activity_on_the_doctor_and_the_hospital(client, crew):
    doctor = company(client, crew["ria"], "Dr. Reyes")
    hospital = company(client, crew["ria"], "Manila Cancer Center")
    a = activity(client, crew["ria"], subject="Detailed Onco One", companyId=doctor["id"], alsoCompanyIds=[hospital["id"]])
    assert a["alsoOn"] == [{"id": hospital["id"], "name": "Manila Cancer Center"}]
    on_hospital = client.get(f"/companies/{hospital['id']}", headers=crew["ria"]).json()["activities"]
    assert [x["subject"] for x in on_hospital] == ["Detailed Onco One"]
    cleared = client.patch(f"/activities/{a['id']}", json={"alsoCompanyIds": []}, headers=crew["ria"]).json()
    assert cleared["alsoOn"] == []
