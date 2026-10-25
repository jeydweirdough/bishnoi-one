"""A product's FDA Certificate of Product Registration (app/cpr.py): kept and
checked on the product, many at once from a spreadsheet, and flagged when it's
missing, without a date, expired or about to expire."""

from datetime import timedelta

from app.out import today


def day(days: int) -> str:
    return (today() + timedelta(days=days)).isoformat()


def test_a_product_keeps_its_cpr_as_the_fda_prints_it(ana, world):
    ana.patch(f"/inventory/products/{world['pcm']}", {"cprNumber": " dr-xy 12345 ", "cprValidUntil": day(400)})
    p = ana.get(f"/inventory/products/{world['pcm']}")
    assert (p["cpr"]["number"], p["cpr"]["validUntil"], p["cpr"]["state"]) == ("DR-XY12345", day(400), "valid")
    bad = ana.c.patch(f"/inventory/products/{world['pcm']}", headers=ana.h, json={"cprNumber": "12345"})
    assert bad.status_code == 422 and "DR-XY12345" in bad.text
    # A date needs the number it belongs to.
    dateless = ana.c.patch(f"/inventory/products/{world['gloves']}", headers=ana.h, json={"cprValidUntil": day(10)})
    assert dateless.status_code == 422 and "CPR number" in dateless.text
    # Cleared, it's missing again.
    ana.patch(f"/inventory/products/{world['pcm']}", {"cprNumber": "", "cprValidUntil": None})
    assert ana.get(f"/inventory/products/{world['pcm']}")["cpr"]["state"] == "missing"


def test_each_state_is_found_by_the_list_and_counted(ana, world):
    ana.patch(f"/inventory/products/{world['pcm']}", {"cprNumber": "DR-XY1", "cprValidUntil": day(-1)})
    ana.patch(f"/inventory/products/{world['gloves']}", {"cprNumber": "CMDR-2", "cprValidUntil": day(30)})
    ana.patch(f"/inventory/products/{world['pump']}", {"cprNumber": "CMDR-3"})
    service = ana.post("/inventory/products", {"sku": "SVC", "name": "Delivery", "productType": "service"})["id"]
    states = {r["sku"]: r["cpr"]["state"] for r in ana.get("/inventory/products")}
    assert states == {"PCM-500": "expired", "GLV-M": "expiring", "PUMP": "no_date", "SVC": "not_needed"}
    for wanted, skus in {"expired": ["PCM-500"], "expiring": ["GLV-M"], "no_date": ["PUMP"], "attention": ["GLV-M", "PUMP", "PCM-500"]}.items():
        assert [r["sku"] for r in ana.get("/inventory/products", cpr=wanted, limit=50)["items"]] == sorted(skus, key=lambda s: {"GLV-M": "gloves m", "PUMP": "infusion pump", "PCM-500": "paracetamol 500mg"}[s])
    summary = ana.get("/inventory/products/cpr/summary")
    assert summary["counts"] == {"missing": 0, "no_date": 1, "expired": 1, "expiring": 1, "valid": 0, "not_needed": 1} and summary["attention"] == 3
    keys = {a["key"]: a for a in ana.get("/inventory/alerts")}
    assert keys["cpr_expired"]["count"] == 1 and "DR-XY1" in keys["cpr_expired"]["examples"][0]
    assert keys["cpr_expiring"]["count"] == 1 and keys["cpr_missing"]["count"] == 1
    report = ana.get("/inventory/reports/registrations")["rows"]
    assert [r["sku"] for r in report] == ["PUMP", "PCM-500", "GLV-M"] and report[1]["state"] == "CPR expired"
    assert service


def test_many_at_once_from_a_spreadsheet_checked_before_saving(ana, world):
    rows = [
        {"sku": "pcm-500", "cprNumber": "DR-XY12345", "validUntil": "31/03/2027"},
        {"sku": "GLV-M", "cprNumber": "not a cpr", "validUntil": "2027-01-01"},
        {"sku": "NOPE", "cprNumber": "DR-1"},
        {"sku": "PCM-500", "cprNumber": "DR-XY9"},
        {"sku": "PUMP", "cprNumber": "CMDR-77", "validUntil": "13/13/2027"},
    ]
    check = ana.post("/inventory/products/cpr", {"rows": rows})
    assert [r["result"] for r in check["rows"]] == ["change", "problem", "problem", "problem", "problem"]
    assert check["rows"][0]["validUntil"] == "2027-03-31" and check["rows"][0]["changes"] == ["CPR number", "valid until"]
    assert "earlier line" in check["rows"][3]["problems"][0] and "No product" in check["rows"][2]["problems"][0]
    assert check["saved"] == 0 and ana.get(f"/inventory/products/{world['pcm']}")["cpr"]["number"] is None  # only checked
    done = ana.post("/inventory/products/cpr", {"rows": rows, "apply": True})
    assert done["saved"] == 1
    assert ana.get(f"/inventory/products/{world['pcm']}")["cpr"]["number"] == "DR-XY12345"
    again = ana.post("/inventory/products/cpr", {"rows": rows[:1]})
    assert again["rows"][0]["result"] == "same"


def test_the_crm_is_given_the_cpr_with_the_products(client, ana, world, app):
    ana.patch(f"/inventory/products/{world['pcm']}", {"cprNumber": "DR-XY12345", "cprValidUntil": "2027-03-31"})
    from app.routers import integration

    with app.state.sessions() as db:  # the integration feed, read directly (its key check is tested in test_integration.py)
        items = {i["sku"]: i for i in integration.products(db)["items"]}
    assert (items["PCM-500"]["cprNumber"], items["PCM-500"]["cprValidUntil"]) == ("DR-XY12345", "2027-03-31")


def test_the_screens_ask_for_them_through_graphql(ana, world):
    ana.patch(f"/inventory/products/{world['pcm']}", {"cprNumber": "DR-XY1", "cprValidUntil": day(-1)})
    r = ana.c.post("/graphql", headers=ana.h, json={"query": '{ products(cpr: "expired", limit: 10) cprSummary }'})
    data = r.json()["data"]
    assert [p["sku"] for p in data["products"]["items"]] == ["PCM-500"] and data["cprSummary"]["counts"]["expired"] == 1
