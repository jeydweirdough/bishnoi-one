"""Possible duplicates, merging them, and saying two are different."""

from app.models import Balance
from tests.test_customers import activity, company, contact, crew  # noqa: F401  (crew is a fixture)


def pairs(client, headers, kind="company") -> list[tuple[set[str], list[str]]]:
    r = client.get(f"/duplicates?kind={kind}", headers=headers)
    assert r.status_code == 200, r.text
    return [({p["a"]["name"], p["b"]["name"]}, p["reasons"]) for p in r.json()["pairs"]]


def merge(client, headers, keep, other, kind="company"):
    return client.post("/duplicates/merge", json={"kind": kind, "keepId": keep, "mergeId": other}, headers=headers)


def test_lookalike_customers_are_found_and_different_ones_are_not(client, crew):
    lia = crew["lia"]
    company(client, lia, "Mercury Drug Makati", city="Makati")
    company(client, lia, "Mercury Drug - Makati Inc.", city="Makati", allowDuplicate=True)
    company(client, lia, "Dr. Jose Santos Clinic", phone="0917 555 0101")
    company(client, lia, "Santos Family Clinic", phone="+63 917 555 0101", allowDuplicate=True)
    company(client, lia, "Mercury Drug Cebu", city="Cebu")
    company(client, lia, "Watsons BGC")
    found = pairs(client, lia)
    assert ({"Mercury Drug Makati", "Mercury Drug - Makati Inc."}, ["Same name", "Same city"]) in found
    assert ({"Dr. Jose Santos Clinic", "Santos Family Clinic"}, ["Same phone number"]) in found
    # Another city's branch isn't the same place.
    assert not any("Mercury Drug Cebu" in names for names, _ in found)
    assert len(found) == 2


def test_only_records_in_reach_are_compared(client, crew):
    company(client, crew["sam"], "Acme Pharma")
    company(client, crew["ria"], "ACME Pharma Inc", allowDuplicate=True)
    assert pairs(client, crew["ria"]) == []
    assert len(pairs(client, crew["max"])) == 1


def test_merging_moves_everything_to_the_kept_customer(app, client, crew):
    lia = crew["lia"]
    keep = company(client, lia, "Mercury Drug Makati", city="Makati")["id"]
    other = company(client, lia, "Mercury Drug Makati", phone="02 8123 4567", email="buy@mercury.test", notes="Pays in 30 days", allowDuplicate=True)["id"]
    maria = contact(client, lia, "Maria", companyId=other)["id"]
    activity(client, lia, companyId=other)
    with app.state.sessions() as db:
        db.add(Balance(company_id=other, as_of="2026-09-30", amount_centavos=150000))
        db.commit()

    r = merge(client, lia, keep, other)
    assert r.status_code == 200, r.text
    assert set(r.json()["filled"]) == {"phone", "email", "notes"}
    kept = client.get(f"/companies/{keep}", headers=lia).json()
    assert (kept["phone"], kept["email"], kept["city"], kept["notes"]) == ("02 8123 4567", "buy@mercury.test", "Makati", "Pays in 30 days")
    assert client.get(f"/contacts/{maria}", headers=lia).json()["company"]["id"] == keep
    assert client.get(f"/activities?company={keep}", headers=lia).json()["total"] == 1
    with app.state.sessions() as db:
        assert db.query(Balance).filter_by(company_id=keep).count() == 1
    # The other one is gone, and its id leads to the one kept.
    assert client.get(f"/companies/{other}", headers=lia).status_code == 404
    assert client.get(f"/merged/{other}", headers=lia).json()["newId"] == keep
    assert pairs(client, lia) == []


def test_merging_needs_delete_and_both_records_in_reach(client, crew):
    ria = company(client, crew["ria"], "Acme Pharma")["id"]
    ria2 = company(client, crew["ria"], "Acme Pharma", allowDuplicate=True)["id"]
    sams = company(client, crew["sam"], "Acme Pharma", allowDuplicate=True)["id"]
    # A salesperson can see possible duplicates but not merge: the other record goes.
    assert len(pairs(client, crew["ria"])) == 1
    assert merge(client, crew["ria"], ria, ria2).status_code == 403
    # Lia leads North: Sam's customer is outside her reach.
    assert merge(client, crew["lia"], ria, sams).status_code == 404
    assert merge(client, crew["lia"], ria, ria).status_code == 422


def test_contacts_with_the_same_name_merge_only_within_a_customer(client, crew):
    lia = crew["lia"]
    acme = company(client, lia, "Acme")["id"]
    beta = company(client, lia, "Beta")["id"]
    keep = contact(client, lia, "Maria", lastName="Santos", companyId=acme)["id"]
    other = contact(client, lia, "Maria", lastName="Santos", companyId=acme, mobile="0918 222 3333", allowDuplicate=True)["id"]
    contact(client, lia, "Maria", lastName="Santos", companyId=beta)
    found = pairs(client, lia, "contact")
    assert found == [({"Maria Santos"}, ["Same name", "Same customer"])]
    activity(client, lia, contactId=other, companyId=acme)
    assert merge(client, lia, keep, other, "contact").status_code == 200
    kept = client.get(f"/contacts/{keep}", headers=lia).json()
    assert kept["mobile"] == "0918 222 3333"
    assert client.get(f"/activities?contact={keep}", headers=lia).json()["total"] == 1


def test_a_pair_said_to_be_different_is_not_offered_again(client, crew):
    lia = crew["lia"]
    a = company(client, lia, "Santos Clinic", phone="0917 555 0101")["id"]
    b = company(client, lia, "Santos Clinic", allowDuplicate=True)["id"]
    assert len(pairs(client, lia)) == 1
    r = client.post("/duplicates/different", json={"kind": "company", "firstId": b, "secondId": a}, headers=lia)
    assert r.status_code == 204
    assert pairs(client, lia) == []


def test_finance_finds_a_merged_customer_under_the_kept_one(app, client, crew):
    lia = crew["lia"]
    keep = company(client, lia, "Mercury Drug")["id"]
    other = company(client, lia, "Mercury Drug", allowDuplicate=True)["id"]
    assert merge(client, lia, keep, other).status_code == 200
    from app.routers.integration import read_customer

    with app.state.sessions() as db:
        assert read_customer("finance", db, other)["id"] == keep
