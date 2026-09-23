"""Settings -> Orders, and the audit log that records who changed what."""


def lists(client, headers) -> dict:
    r = client.get("/admin/orders", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_getmeds_starts_with_its_old_order_lists(client, as_):
    data = lists(client, as_("carmen"))
    assert [k["kind"] for k in data["kinds"]] == [
        "payment_method", "payment_term", "source", "delivery_method", "invoicing_entity", "field_section"
    ]
    assert [i["name"] for i in data["lists"]["invoicing_entity"]] == ["2mg Incorporated", "Getmeds Philippines Inc."]
    assert "GCash" in {i["name"] for i in data["lists"]["payment_method"]}
    assert len(data["lists"]["payment_term"]) == 23
    assert data["rules"] == {"largeOrderCentavos": 10_000_000, "recycleDays": 30, "orderPrefix": "GM", "currency": "PHP"}


def test_only_admins_see_order_settings(client, as_):
    assert client.get("/admin/orders", headers=as_("ana")).status_code == 403


def test_a_list_is_saved_whole_in_its_order(client, as_):
    carmen = as_("carmen")
    methods = lists(client, carmen)["lists"]["delivery_method"]
    first, *rest = methods
    body = {"items": [*rest[:2], {"name": "Motorcycle courier"}, {**first, "name": "Company vehicle", "isActive": False}]}
    r = client.put("/admin/orders/lists/delivery_method", json=body, headers=carmen)
    assert r.status_code == 200, r.text
    saved = r.json()["lists"]["delivery_method"]
    assert [i["name"] for i in saved] == [rest[0]["name"], rest[1]["name"], "Motorcycle courier", "Company vehicle"]
    assert saved[2]["code"] == "motorcycle-courier"
    assert saved[3]["code"] == first["code"] and saved[3]["isActive"] is False  # renamed, same code


def test_list_mistakes_land_on_the_right_item(client, as_):
    carmen = as_("carmen")
    r = client.put("/admin/orders/lists/source", json={"items": [{"name": "Phone"}, {"name": "phone"}]}, headers=carmen)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "items", 1, "name"]
    r = client.put("/admin/orders/lists/source", json={"items": [{"code": "made-up", "name": "X"}]}, headers=carmen)
    assert r.status_code == 422
    assert client.put("/admin/orders/lists/colours", json={"items": []}, headers=carmen).status_code == 404


def test_extra_fields(client, as_):
    carmen = as_("carmen")
    body = {"fields": [
        {"label": "PO number", "type": "text", "required": True, "help": "From the hospital's purchase order"},
        {"label": "Cold chain", "type": "choice", "options": ["Yes", "No", "Yes"]},
    ]}
    r = client.put("/admin/orders/fields", json=body, headers=carmen)
    assert r.status_code == 200, r.text
    fields = r.json()["fields"]
    assert [(f["key"], f["type"], f["required"]) for f in fields] == [("po_number", "text", True), ("cold_chain", "choice", False)]
    assert fields[1]["options"] == ["Yes", "No"]

    one_option = {"fields": [{"label": "Cold chain", "type": "choice", "options": ["Yes"]}]}
    r = client.put("/admin/orders/fields", json=one_option, headers=carmen)
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "fields", 0, "options"]


def test_rules(client, as_):
    carmen = as_("carmen")
    r = client.put("/admin/orders/rules", json={"largeOrderCentavos": 5_000_000, "recycleDays": 45, "orderPrefix": "GMX"}, headers=carmen)
    assert r.status_code == 200, r.text
    assert r.json()["rules"]["orderPrefix"] == "GMX" and r.json()["rules"]["recycleDays"] == 45
    bad = client.put("/admin/orders/rules", json={"largeOrderCentavos": 1, "recycleDays": 0, "orderPrefix": "gm-1"}, headers=carmen)
    assert bad.status_code == 422


def test_changes_are_audited_by_name_never_by_value(client, as_):
    carmen = as_("carmen")
    client.put("/admin/orders/rules", json={"largeOrderCentavos": 7_500_000, "recycleDays": 30, "orderPrefix": "GM"}, headers=carmen)
    ana = next(u["id"] for u in client.get("/admin/users", headers=carmen).json() if u["email"] == "ana@pharmacrm.test")
    client.patch(f"/admin/users/{ana}", json={"password": "a-new-password-1"}, headers=carmen)

    entries = client.get("/admin/audit", headers=carmen).json()["items"]
    person, rules = entries[0], entries[1]
    assert person["action"] == "person.updated" and person["target"] == "ana@pharmacrm.test" and person["fields"] == ["password"]
    assert rules["action"] == "orders.rules_changed" and rules["fields"] == ["largeOrderCentavos"]
    assert all(e["actor"] == "carmen@pharmacrm.test" for e in entries[:2])
    text = str(entries)
    assert "a-new-password-1" not in text and "7500000" not in text


def test_the_audit_log_pages_and_is_admin_only(client, as_):
    carmen = as_("carmen")
    for days in (31, 32, 33):
        client.put("/admin/orders/rules", json={"largeOrderCentavos": 10_000_000, "recycleDays": days, "orderPrefix": "GM"}, headers=carmen)
    page = client.get("/admin/audit", params={"limit": 2}, headers=carmen).json()
    assert len(page["items"]) == 2 and page["more"] is True
    rest = client.get("/admin/audit", params={"limit": 2, "before": page["items"][-1]["at"]}, headers=carmen).json()
    assert rest["items"] and rest["items"][0]["id"] not in {e["id"] for e in page["items"]}
    assert client.get("/admin/audit", headers=as_("ana")).status_code == 403


def test_customer_changes_are_audited(client, as_):
    ana = as_("ana")
    r = client.post("/sales/customers", json={"division": "bnb", "team": "md-telesales", "name": "Dr. New Person", "kind": "doctor"}, headers=ana)
    assert r.status_code == 201, r.text
    client.patch(f"/sales/customers/{r.json()['id']}", json={"phone": "0917 000 1111"}, headers=ana)
    entries = client.get("/admin/audit", headers=as_("carmen")).json()["items"]
    assert [e["action"] for e in entries[:2]] == ["customer.updated", "customer.created"]
    assert "phone" in entries[0]["fields"] and "0917" not in str(entries[0])
