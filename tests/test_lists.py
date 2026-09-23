"""Settings -> Lists: the choices a company keeps for its own records.

What matters here is that a company can change what it calls things without a
developer, and that changing them never strands a record that already carries
the old choice.
"""

def kinds(client, headers) -> dict:
    return client.get("/admin/lists", headers=headers).json()


def codes(client, headers, kind: str) -> list[str]:
    return [i["code"] for i in kinds(client, headers)["lists"][kind]]


def test_a_company_starts_with_the_lists_it_used_to_have_in_code(client, as_):
    carmen = as_("carmen")
    payload = kinds(client, carmen)
    assert [k["kind"] for k in payload["kinds"]] == ["customer_kind", "activity_kind", "outcome"]
    assert codes(client, carmen, "customer_kind") == [
        "doctor", "hospital", "clinic", "pharmacy", "patient", "company", "distributor", "other"
    ]
    # activity kinds carry an icon; the other lists don't
    activities = payload["lists"]["activity_kind"]
    assert [(a["code"], a["icon"]) for a in activities] == [
        ("call", "call"), ("visit", "visit"), ("message", "message"), ("note", "note")
    ]
    assert all(i["icon"] is None for i in payload["lists"]["customer_kind"])


def test_renaming_a_choice_keeps_its_code_so_records_still_match(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    items = kinds(client, carmen)["lists"]["customer_kind"]
    body = {"items": [{**i, "name": "Prescriber" if i["code"] == "doctor" else i["name"]} for i in items]}
    r = client.put("/admin/lists/customer_kind", json=body, headers=carmen)
    assert r.status_code == 200
    renamed = next(i for i in r.json()["lists"]["customer_kind"] if i["code"] == "doctor")
    assert renamed["name"] == "Prescriber"
    # a customer can still be created with it, and everyone sees the new name
    made = client.post("/sales/customers", json={"division": "bnb", "team": "general", "name": "Dr Reyes", "kind": "doctor"}, headers=lorna)
    assert made.status_code == 201
    assert next(i for i in client.get("/auth/me", headers=lorna).json()["lists"]["customer_kind"] if i["code"] == "doctor")[
        "name"
    ] == "Prescriber"


def test_a_company_adds_its_own_kind_and_uses_it(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    items = kinds(client, carmen)["lists"]["customer_kind"]
    body = {"items": [*items, {"name": "Veterinary clinic"}]}
    r = client.put("/admin/lists/customer_kind", json=body, headers=carmen)
    assert r.status_code == 200
    assert "veterinary-clinic" in [i["code"] for i in r.json()["lists"]["customer_kind"]]
    made = client.post("/sales/customers", json={"division": "bnb", "team": "general", "name": "Pet Care Centre", "kind": "veterinary-clinic"}, headers=lorna)
    assert made.status_code == 201 and made.json()["kind"] == "veterinary-clinic"


def test_a_kind_this_company_does_not_keep_is_refused(client, as_):
    lorna = as_("lorna")
    r = client.post("/sales/customers", json={"division": "bnb", "team": "general", "name": "Nobody", "kind": "spaceship"}, headers=lorna)
    assert r.status_code == 422
    assert "Settings" in str(r.json()["detail"])


def test_switching_a_choice_off_keeps_the_records_that_have_it(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    made = client.post("/sales/customers", json={"division": "bnb", "team": "general", "name": "Old Pharmacy", "kind": "pharmacy"}, headers=lorna)
    assert made.status_code == 201
    customer_id = made.json()["id"]

    items = kinds(client, carmen)["lists"]["customer_kind"]
    body = {"items": [{**i, "isActive": i["code"] != "pharmacy"} for i in items]}
    assert client.put("/admin/lists/customer_kind", json=body, headers=carmen).status_code == 200

    # the record is untouched and still readable
    assert client.get(f"/sales/customers/{customer_id}", headers=lorna).json()["kind"] == "pharmacy"
    # but nobody can pick it again
    again = client.post("/sales/customers", json={"division": "bnb", "team": "general", "name": "New Pharmacy", "kind": "pharmacy"}, headers=lorna)
    assert again.status_code == 422
    # the screens are told it exists and is off, so they can still name the
    # records that carry it while offering only the live ones
    offered = {i["code"]: i for i in client.get("/auth/me", headers=lorna).json()["lists"]["customer_kind"]}
    assert offered["pharmacy"]["isActive"] is False
    assert offered["clinic"]["isActive"] is True


def test_a_required_list_cannot_be_emptied(client, as_):
    carmen = as_("carmen")
    items = kinds(client, carmen)["lists"]["customer_kind"]
    body = {"items": [{**i, "isActive": False} for i in items]}
    r = client.put("/admin/lists/customer_kind", json=body, headers=carmen)
    assert r.status_code == 422 and "at least one" in str(r.json()["detail"])


def test_an_outcome_is_optional_and_checked(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    made = client.post("/sales/customers", json={"division": "bnb", "team": "general", "name": "Clinic One", "kind": "clinic"}, headers=lorna)
    customer_id = made.json()["id"]
    good = {"kind": "call", "summary": "Rang about the new promo", "outcome": "reached"}
    assert client.post(f"/sales/customers/{customer_id}/activities", json=good, headers=lorna).status_code == 201
    bad = {"kind": "call", "summary": "Rang again", "outcome": "delighted"}
    assert client.post(f"/sales/customers/{customer_id}/activities", json=bad, headers=lorna).status_code == 422
    # a company can add its own
    outcomes = kinds(client, carmen)["lists"]["outcome"]
    client.put("/admin/lists/outcome", json={"items": [*outcomes, {"name": "Delighted"}]}, headers=carmen)
    assert client.post(f"/sales/customers/{customer_id}/activities", json={**bad, "outcome": "delighted"}, headers=lorna).status_code == 201


def test_each_company_keeps_its_own_lists(client, as_, acme):
    carmen = as_("carmen")
    items = kinds(client, carmen)["lists"]["customer_kind"]
    client.put(
        "/admin/lists/customer_kind",
        json={"items": [{**i, "name": "Prescriber" if i["code"] == "doctor" else i["name"]} for i in items]},
        headers=carmen,
    )
    theirs = client.get("/admin/lists", headers=acme).json()["lists"]["customer_kind"]
    # Acme was made from the generic template, so it never had "Doctor" at all
    assert "Prescriber" not in [i["name"] for i in theirs]
    assert [i["name"] for i in theirs] == ["Company", "Individual", "Reseller", "Other"]


def test_only_a_settings_admin_may_change_a_list(client, as_):
    lorna = as_("lorna")
    assert client.get("/admin/lists", headers=lorna).status_code == 403
    assert client.put("/admin/lists/customer_kind", json={"items": []}, headers=lorna).status_code == 403


def test_a_renamed_then_retired_choice_still_names_its_records(client, as_):
    """The case that loses a name if only live choices are sent: renamed and
    switched off in one go, the records filed under it must still read the new
    name rather than falling back to the bare code."""
    carmen, lorna = as_("carmen"), as_("lorna")
    items = kinds(client, carmen)["lists"]["customer_kind"]
    body = {
        "items": [
            {**i, "name": "Prescriber" if i["code"] == "doctor" else i["name"], "isActive": i["code"] != "doctor"}
            for i in items
        ]
    }
    assert client.put("/admin/lists/customer_kind", json=body, headers=carmen).status_code == 200

    seen = {i["code"]: i for i in client.get("/auth/me", headers=lorna).json()["lists"]["customer_kind"]}
    assert seen["doctor"]["name"] == "Prescriber" and seen["doctor"]["isActive"] is False
