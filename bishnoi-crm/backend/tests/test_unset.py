"""The sidebar's red counts: what isn't set up yet, for whoever can fix it."""

from tests.test_customers import crew  # noqa: F401 (a fixture)
from tests.test_quotes import catalogue, ids  # noqa: F401 (fixtures)


def test_a_product_with_no_price_is_counted_for_who_can_price_it(client, ana, crew, ids):  # noqa: F811
    before = client.get("/unset", headers=ana).json().get("productPrices", 0)
    made = client.post("/products", json={"code": "NP-1", "name": "Nopricin", "unit": "box", "prices": {"PATIENT": 5000}}, headers=ana).json()
    assert client.get("/unset", headers=ana).json()["productPrices"] == before + 1
    # The list shows the same ones.
    missing = client.get("/products?missing=true", headers=ana).json()
    assert made["id"] in [p["id"] for p in missing["items"]] and missing["total"] == missing["missingPrices"] == before + 1
    # Priced at every listed type, it's done; switched off, it doesn't count.
    listed = [t["code"] for t in client.get("/pricing", headers=ana).json()["priceTypes"] if t["entry"] == "list" and t["isActive"]]
    client.patch(f"/products/{made['id']}", json={"prices": {c: 5000 for c in listed}}, headers=ana)
    assert client.get("/unset", headers=ana).json().get("productPrices", 0) == before
    # A salesperson can't price products, so it isn't theirs to see.
    assert "productPrices" not in client.get("/unset", headers=crew["ria"]).json()


def test_setup_an_admin_owes(client, ana, ben):
    got = client.get("/unset", headers=ana).json()
    assert got["quoteTemplates"] == 1 and got["companyDetails"] == 3
    r = client.patch("/admin/company-settings", json={"companyAddress": "1 Ayala Ave", "companyTin": "123-456", "companyContact": "02 8123 4567"}, headers=ana)
    assert r.status_code == 200, r.text
    assert "companyDetails" not in client.get("/unset", headers=ana).json()
    assert client.get("/unset", headers=ben).json() == {}
