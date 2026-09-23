"""Settings -> Fields: the fields a company puts on its own records.

What matters here is that a company can describe what it sells in its own
words without a developer, that one company's words never reach another's, and
that changing the fields never strands a record that already has values.
"""

from tests.conftest import field_messages


def fields(client, headers, subject: str = "product") -> list[dict]:
    r = client.get("/admin/fields", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["fields"][subject]


def save(client, headers, sent: list[dict], subject: str = "product"):
    return client.put(f"/admin/fields/{subject}", json={"fields": sent}, headers=headers)


def product(client, headers, code: str) -> dict:
    products = client.get("/inventory/products", params={"q": code}, headers=headers).json()
    return next(p for p in products if p["code"] == code.upper())


def test_a_pharmacy_starts_with_the_fields_its_products_used_to_have(client, as_, acme):
    carmen = as_("carmen")
    assert [(f["key"], f["label"], f["type"]) for f in fields(client, carmen)] == [
        ("generic_name", "Generic name", "text"),
        ("strength", "Strength", "text"),
        ("form", "Form", "text"),
    ]
    payload = client.get("/admin/fields", headers=carmen).json()
    assert [s["subject"] for s in payload["subjects"]] == ["order", "product", "customer"]
    assert payload["fields"]["customer"] == []
    # Acme sells hardware: it starts with nothing and writes its own.
    assert fields(client, acme) == [] and fields(client, acme, "customer") == []


def test_a_field_a_company_adds_is_one_its_products_can_be_saved_with(client, as_):
    carmen, iris = as_("carmen"), as_("iris")
    kept = [{**f, "key": f["key"]} for f in fields(client, carmen)]
    added = [*kept, {"label": "Shelf life", "type": "choice", "options": ["12 months", "24 months"]}]
    assert save(client, carmen, added).status_code == 200

    # Inventory staff aren't admins, so the product form reads the fields here.
    reference = client.get("/inventory/reference", headers=iris).json()
    assert [f["key"] for f in reference["fields"]] == ["generic_name", "strength", "form", "shelf_life"]

    body = {"code": "cef-250", "name": "Cefalexin 250 mg", "unit": "Box of 100",
            "details": {"generic_name": "Cefalexin", "shelf_life": "24 months"}}
    r = client.post("/inventory/products", json=body, headers=iris)
    assert r.status_code == 201, r.text
    assert r.json()["details"] == {"generic_name": "Cefalexin", "shelf_life": "24 months"}
    # The web app still reads the pharma three by name, from the same values.
    assert r.json()["genericName"] == "Cefalexin"

    r = client.patch(f"/inventory/products/{r.json()['id']}", json={"details": {"shelf_life": "12 months"}}, headers=iris)
    assert r.status_code == 200 and r.json()["details"] == {"shelf_life": "12 months"}
    # Searching finds a product by what its own fields hold, not just its name.
    found = client.get("/inventory/products", params={"q": "12 months"}, headers=iris).json()
    assert [p["code"] for p in found] == ["CEF-250"]


def test_a_value_that_breaks_the_rules_says_which_field_and_why(client, as_):
    carmen, iris = as_("carmen"), as_("iris")
    generic = next(f for f in fields(client, carmen) if f["key"] == "generic_name")
    sent = [
        {**generic, "required": True},
        {"label": "Shelf life", "type": "choice", "options": ["12 months", "24 months"]},
        {"label": "Pack size", "type": "number"},
    ]
    assert save(client, carmen, sent).status_code == 200
    base = {"code": "cef-250", "name": "Cefalexin 250 mg", "unit": "Box of 100"}

    r = client.post("/inventory/products", json={**base, "details": {"pack_size": 10}}, headers=iris)
    assert r.status_code == 422
    assert field_messages(r)["details.generic_name"] == "Generic name is needed."

    r = client.post(
        "/inventory/products",
        json={**base, "details": {"generic_name": "Cefalexin", "shelf_life": "36 months", "pack_size": "a dozen"}},
        headers=iris,
    )
    assert r.status_code == 422
    assert field_messages(r) == {
        "details.shelf_life": "Pick one of the choices for Shelf life.",
        "details.pack_size": "Pack size should be a number.",
    }

    r = client.post("/inventory/products", json={**base, "details": {"generic_name": "X", "colour": "red"}}, headers=iris)
    assert r.status_code == 422
    assert field_messages(r)["details.colour"] == 'Your company has no product field called "colour".'


def test_switching_a_field_off_keeps_the_products_that_have_it(client, as_):
    carmen, iris = as_("carmen"), as_("iris")
    r = client.post(
        "/inventory/products",
        json={"code": "cef-250", "name": "Cefalexin 250 mg", "unit": "Box of 100", "details": {"strength": "250 mg"}},
        headers=iris,
    )
    assert r.status_code == 201, r.text
    product_id = r.json()["id"]

    kept = fields(client, carmen)
    assert save(client, carmen, [f for f in kept if f["key"] != "strength"]).status_code == 200
    off = next(f for f in fields(client, carmen) if f["key"] == "strength")
    assert off["isActive"] is False  # switched off, not deleted: products still carry it

    still = client.get(f"/inventory/products/{product_id}", headers=iris).json()
    assert still["details"] == {"strength": "250 mg"} and still["strength"] == "250 mg"
    # And it can be saved again, so an edit of an old product isn't refused.
    r = client.patch(f"/inventory/products/{product_id}", json={"details": {"strength": "250 mg"}}, headers=iris)
    assert r.status_code == 200, r.text


def test_one_companys_fields_are_never_anothers(client, as_, acme):
    carmen = as_("carmen")
    assert save(client, acme, [{"label": "Model", "type": "text"}]).status_code == 200
    assert [f["key"] for f in fields(client, acme)] == ["model"]
    assert [f["key"] for f in fields(client, carmen)] == ["generic_name", "strength", "form"]

    # Acme's own field, on Acme's own product; Getmeds' words mean nothing here.
    acme_id = next(p["id"] for p in client.get("/inventory/products", headers=acme).json() if p["code"] == "ACME-BOLT")
    r = client.patch(f"/inventory/products/{acme_id}", json={"details": {"model": "M8"}}, headers=acme)
    assert r.status_code == 200 and r.json()["details"] == {"model": "M8"}
    r = client.patch(f"/inventory/products/{acme_id}", json={"details": {"strength": "250 mg"}}, headers=acme)
    assert r.status_code == 422 and "no product field" in field_messages(r)["details.strength"]


def test_customers_carry_their_companys_fields_too(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    sent = [{"label": "Hospital bed count", "type": "number"}, {"label": "Accreditation", "type": "date"}]
    assert save(client, carmen, sent, "customer").status_code == 200

    body = {"team": "general", "name": "Dr Reyes", "kind": "doctor",
            "details": {"hospital_bed_count": 120, "accreditation": "2026-03-31"}}
    r = client.post("/sales/customers", json={"division": "bnb", **body}, headers=lorna)
    assert r.status_code == 201, r.text
    customer_id = r.json()["id"]
    assert r.json()["details"] == {"hospital_bed_count": 120, "accreditation": "2026-03-31"}
    assert client.get(f"/sales/customers/{customer_id}", headers=lorna).json()["details"]["hospital_bed_count"] == 120

    r = client.patch(f"/sales/customers/{customer_id}", json={"details": {"accreditation": "soon"}}, headers=lorna)
    assert r.status_code == 422
    assert field_messages(r)["details.accreditation"] == "Accreditation should be a date, like 2026-03-31."


def test_only_admins_change_the_fields(client, as_):
    iris = as_("iris")
    assert client.get("/admin/fields", headers=iris).status_code == 403
    assert save(client, iris, [{"label": "Model", "type": "text"}]).status_code == 403
    assert save(client, as_("ana"), [{"label": "Model", "type": "text"}]).status_code == 403
    # Order fields have their own screen; this one shows them and sends people there.
    r = save(client, as_("carmen"), [{"label": "PO number", "type": "text"}], "order")
    assert r.status_code == 422 and "Settings -> Orders" in r.json()["detail"]


def test_the_pharma_columns_came_across_into_the_fields(client, as_):
    """The three values a seeded product was made with are its field values now."""
    amox = product(client, as_("iris"), "AMOX-500")
    assert amox["details"] == {"generic_name": "Amoxicillin", "strength": "500 mg", "form": "Capsule"}
    assert (amox["genericName"], amox["strength"], amox["form"]) == ("Amoxicillin", "500 mg", "Capsule")


def test_a_rep_is_told_the_companys_customer_fields(client, as_):
    """A rep fills the customer form but is not an admin, so the fields ride
    along with their sign-in rather than a settings call they can't make."""
    carmen, lorna = as_("carmen"), as_("lorna")
    assert client.get("/auth/me", headers=lorna).json()["customerFields"] == []

    body = {"fields": [{"label": "Hospital group", "type": "text", "required": False, "options": [], "help": ""}]}
    assert client.put("/admin/fields/customer", json=body, headers=carmen).status_code == 200

    fields = client.get("/auth/me", headers=lorna).json()["customerFields"]
    assert [(f["key"], f["label"], f["type"]) for f in fields] == [("hospital_group", "Hospital group", "text")]

    # and a rep can then save a customer carrying it
    made = client.post(
        "/sales/customers",
        json={
            "division": "bnb",
            "team": "general",
            "name": "St Luke's",
            "kind": "hospital",
            "details": {"hospital_group": "Quezon City"},
        },
        headers=lorna,
    )
    assert made.status_code == 201, made.text
    assert made.json()["details"] == {"hospital_group": "Quezon City"}

    # switched off, it leaves the form but the record keeps its value
    off = {"fields": [{**fields[0], "isActive": False, "options": [], "help": ""}]}
    assert client.put("/admin/fields/customer", json=off, headers=carmen).status_code == 200
    assert client.get("/auth/me", headers=lorna).json()["customerFields"] == []
    kept = client.get(f"/sales/customers/{made.json()['id']}", headers=lorna).json()
    assert kept["details"] == {"hospital_group": "Quezon City"}


def order_fields(client, headers) -> list[dict]:
    return client.get("/admin/orders", headers=headers).json()["fields"]


def test_an_order_field_sits_in_a_part_of_the_form(client, as_):
    """The old Orders app groups its form into four parts and puts each extra
    field in one. Without that, a rebuilt form is one long heap."""
    carmen = as_("carmen")
    settings = client.get("/admin/orders", headers=carmen).json()
    sections = {i["code"]: i["name"] for i in settings["lists"]["field_section"]}
    assert list(sections.values()) == ["Order Details", "Billing & Payment", "Logistics & Delivery", "Additional Information"]

    body = {
        "fields": [
            {"label": "Doctor's name", "type": "text", "required": False, "options": [], "help": "", "section": "order-details"},
            {"label": "PO number", "type": "text", "required": False, "options": [], "help": "", "section": "billing-payment"},
            {"label": "Anything else", "type": "textarea", "required": False, "options": [], "help": ""},
        ]
    }
    r = client.put("/admin/orders/fields", json=body, headers=carmen)
    assert r.status_code == 200, r.text
    placed = {f["label"]: f["section"] for f in r.json()["fields"]}
    assert placed == {"Doctor's name": "order-details", "PO number": "billing-payment", "Anything else": None}


def test_a_section_this_company_does_not_keep_is_refused(client, as_):
    carmen = as_("carmen")
    body = {"fields": [{"label": "Stray", "type": "text", "required": False, "options": [], "help": "", "section": "nowhere"}]}
    r = client.put("/admin/orders/fields", json=body, headers=carmen)
    assert r.status_code == 422 and "form sections" in str(r.json()["detail"])


def test_the_sections_are_a_list_a_company_can_change(client, as_):
    """They are a pick-list like any other, not four words in the code."""
    carmen = as_("carmen")
    settings = client.get("/admin/orders", headers=carmen).json()
    items = settings["lists"]["field_section"]
    renamed = [{**i, "name": "Delivery" if i["code"] == "logistics-delivery" else i["name"]} for i in items]
    r = client.put("/admin/orders/lists/field_section", json={"items": renamed}, headers=carmen)
    assert r.status_code == 200
    assert "Delivery" in [i["name"] for i in r.json()["lists"]["field_section"]]
    # the code is unchanged, so a field already sitting there is not stranded
    assert "logistics-delivery" in [i["code"] for i in r.json()["lists"]["field_section"]]


def test_a_company_from_the_plain_template_gets_its_own_wording(client, acme):
    settings = client.get("/admin/orders", headers=acme).json()
    assert [i["name"] for i in settings["lists"]["field_section"]] == ["Details", "Payment", "Delivery", "Anything else"]
