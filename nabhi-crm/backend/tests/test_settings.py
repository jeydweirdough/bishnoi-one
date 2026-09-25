"""Settings: the forms (every field on each record's form, built in or added),
and company & quote settings."""

import json

from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids, line  # noqa: F401 (fixtures)


def errors(r) -> dict[str, str]:
    return {".".join(str(p) for p in e["loc"][1:]): e["msg"] for e in r.json()["detail"]}


def form(client, headers, entity):
    return client.get(f"/forms/{entity}?all=true", headers=headers).json()


def put(client, headers, entity, layout):
    """Sends the layout back the way the editor does: sections with their fields."""
    keys = ("id", "label", "type", "required", "hidden", "inList", "options", "helpText", "placeholder")
    body = {
        "sections": [
            {"id": s.get("id"), "title": s["title"], "columns": s["columns"], "fields": [{k: f[k] for k in keys if k in f} for f in s["fields"]]}
            for s in layout["sections"]
        ]
    }
    return client.put(f"/admin/forms/{entity}", json=body, headers=headers)


def by_key(layout) -> dict:
    return {f["key"]: f for s in layout["sections"] for f in s["fields"]}


def copy(layout):
    return json.loads(json.dumps(layout))


def test_every_form_starts_with_its_built_in_fields(client, crew):
    layout = client.get("/forms/company", headers=crew["ria"]).json()  # anyone reads it
    assert [s["title"] for s in layout["sections"]] == ["The customer", "How to reach them", "Who looks after it"]
    fields = by_key(layout)
    assert fields["name"]["locked"] and fields["name"]["required"] and fields["industry"]["type"] == "choice"
    assert "Hospital" in fields["industry"]["options"]
    assert by_key(client.get("/forms/product", headers=crew["ria"]).json())["unit"]["locked"]


def test_an_admin_shapes_the_company_form(client, crew, ana):
    layout = form(client, ana, "company")
    assert put(client, crew["max"], "company", layout).status_code == 403
    # A new section with two added fields, the website hidden, industry required, a section renamed.
    layout["sections"][0]["title"] = "Company"
    for f in layout["sections"][0]["fields"]:
        if f["key"] == "website":
            f["hidden"] = True
        if f["key"] == "industry":
            f["required"] = True
            f["options"] = ["Hospital", "Clinic", "Pharmacy"]
    layout["sections"].append(
        {
            "title": "Account",
            "columns": 1,
            "fields": [
                {"label": "Beds", "type": "number", "inList": True},
                {"label": "Account tier", "type": "multi_choice", "options": ["Gold", "Silver", "gold"], "required": True},
            ],
        }
    )
    # Moving a field between sections: email goes to the top.
    reach = layout["sections"][1]
    email = next(f for f in reach["fields"] if f["key"] == "email")
    reach["fields"].remove(email)
    layout["sections"][0]["fields"].insert(1, email)
    r = put(client, ana, "company", layout)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert [s["title"] for s in saved["sections"]] == ["Company", "How to reach them", "Who looks after it", "Account"]
    assert [f["key"] for f in saved["sections"][0]["fields"]][:2] == ["name", "email"]
    fields = by_key(saved)
    assert (fields["x_beds"]["type"], fields["x_account_tier"]["options"]) == ("number", ["Gold", "Silver"])
    # Hidden fields drop off the form people fill in.
    assert "website" not in by_key(client.get("/forms/company", headers=crew["ria"]).json())

    # The form is what's checked: industry is required now, and so is the tier.
    r = client.post("/companies", json={"name": "Acme"}, headers=crew["ria"])
    assert "extra.x_account_tier" in errors(r)
    r = client.post("/companies", json={"name": "Acme", "extra": {"x_account_tier": ["Gold"]}}, headers=crew["ria"])
    assert "industry" in errors(r)
    acme = company(client, crew["ria"], "Acme", industry="Clinic", extra={"x_beds": "1,200", "x_account_tier": ["Silver", "Gold"]})
    assert acme["extra"] == {"x_beds": 1200, "x_account_tier": ["Gold", "Silver"]}
    assert "industry" in errors(client.patch(f"/companies/{acme['id']}", json={"industry": None}, headers=crew["ria"]))

    # Locked fields stay: always shown, always required.
    saved["sections"][0]["fields"][0]["hidden"] = True
    saved["sections"][0]["fields"][0]["required"] = False
    after = by_key(put(client, ana, "company", saved).json())
    assert (after["name"]["hidden"], after["name"]["required"]) == (False, True)


def test_what_a_form_cant_lose(client, crew, ana):
    layout = form(client, ana, "company")
    layout["sections"].append({"title": "Extra", "columns": 2, "fields": [{"label": "Beds", "type": "number"}]})
    layout = put(client, ana, "company", layout).json()
    company(client, crew["ria"], "Acme", extra={"x_beds": 5})
    # A built-in field can't be taken off, only hidden.
    no_name = copy(layout)
    no_name["sections"][0]["fields"] = [f for f in no_name["sections"][0]["fields"] if f["key"] != "name"]
    assert "hide it instead" in put(client, ana, "company", no_name).json()["detail"]
    # An added field with values can't be deleted either.
    no_beds = copy(layout)
    no_beds["sections"] = no_beds["sections"][:-1]
    r = put(client, ana, "company", no_beds)
    assert r.status_code == 422 and "1 record has a value in Beds" in r.json()["detail"]
    # Two fields with one name, or a dropdown with one option: refused.
    twice = copy(layout)
    twice["sections"][-1]["fields"].append({"label": "beds", "type": "text"})
    assert "Two fields are called" in put(client, ana, "company", twice).json()["detail"]
    lonely = copy(layout)
    lonely["sections"][-1]["fields"].append({"label": "Tier", "type": "choice", "options": ["Gold"]})
    assert "at least two options" in put(client, ana, "company", lonely).json()["detail"]
    # An empty section is fine.
    more = copy(layout)
    more["sections"].append({"title": "Later", "columns": 2, "fields": []})
    assert [s["title"] for s in put(client, ana, "company", more).json()["sections"]][-1] == "Later"


def test_added_fields_on_products_and_quotes(client, crew, ana, ids):
    for entity, field in (("product", {"label": "FDA number", "type": "text"}), ("quote", {"label": "Delivery date", "type": "date"})):
        layout = form(client, ana, entity)
        layout["sections"][0]["fields"].append(field)
        assert put(client, ana, entity, layout).status_code == 200
    p = client.patch(f"/products/{ids['AMX-500']}", json={"extra": {"x_fda_number": "DR-XY12345"}}, headers=ana).json()
    assert p["extra"] == {"x_fda_number": "DR-XY12345"}
    acme = company(client, crew["ria"])
    body = {"priceType": "PATIENT", "lines": [line(ids["AMX-500"])], "extra": {"x_delivery_date": "not a date"}}
    r = client.post(f"/companies/{acme['id']}/quotes", data={"quote": json.dumps(body)}, headers=crew["ria"])
    assert "extra.x_delivery_date" in errors(r)
    body["extra"] = {"x_delivery_date": "2026-10-01"}
    q = client.post(f"/companies/{acme['id']}/quotes", data={"quote": json.dumps(body)}, headers=crew["ria"]).json()
    assert q["extra"] == {"x_delivery_date": "2026-10-01"}


def test_company_and_quote_settings(client, crew, ana, ids):
    assert client.get("/admin/company-settings", headers=crew["max"]).status_code == 403
    r = client.patch("/admin/company-settings", json={"timezone": "Mars/Base"}, headers=ana)
    assert "timezone" in errors(r)
    s = client.patch(
        "/admin/company-settings",
        json={"orgName": "Getmeds", "currency": "USD", "timezone": "Asia/Singapore", "quotePrefix": "GM", "quoteValidDays": 15, "quoteTerms": "Prices include VAT."},
        headers=ana,
    ).json()
    assert (s["orgName"], s["currency"], s["timezone"], s["quotePrefix"]) == ("Getmeds", "USD", "Asia/Singapore", "GM")
    me = client.get("/auth/me", headers=crew["ria"]).json()
    assert (me["org"]["name"], me["org"]["currency"], me["org"]["timezone"]) == ("Getmeds", "USD", "Asia/Singapore")
    acme = company(client, crew["ria"])
    body = {"priceType": "PATIENT", "lines": [line(ids["AMX-500"])]}
    q = client.post(f"/companies/{acme['id']}/quotes", data={"quote": json.dumps(body)}, headers=crew["ria"]).json()
    assert q["number"].startswith("GM-") and q["terms"] == "Prices include VAT." and q["validUntil"]


def test_a_choice_is_added_from_the_form_it_is_missing_from(client, crew, ana):
    """Filling in a customer, the industry isn't on the list: an admin adds it
    there and then (once, however it's capitalised)."""
    industry = next(f for s in client.get("/forms/company", headers=ana).json()["sections"] for f in s["fields"] if f["key"] == "industry")
    before = len(industry["options"])
    added = client.post("/admin/forms/company/fields/industry/options", json={"label": "Veterinary clinic"}, headers=ana).json()
    assert added["option"] == "Veterinary clinic" and len(added["field"]["options"]) == before + 1
    again = client.post("/admin/forms/company/fields/industry/options", json={"label": "veterinary CLINIC"}, headers=ana).json()
    assert again["option"] == "Veterinary clinic" and len(again["field"]["options"]) == before + 1
    # Not an admin's settings to change otherwise; and only lists take choices.
    assert client.post("/admin/forms/company/fields/industry/options", json={"label": "X"}, headers=crew["ria"]).status_code == 403
    assert client.post("/admin/forms/company/fields/name/options", json={"label": "X"}, headers=ana).status_code == 404
