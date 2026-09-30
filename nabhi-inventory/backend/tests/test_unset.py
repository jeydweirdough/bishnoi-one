"""The sidebar's red counts: what isn't set up yet, for whoever can fix it."""

from tests.conftest import Api


def test_a_product_with_no_price_is_counted_for_who_can_price_it(client, people, ana, world):
    # Paracetamol has no selling price and the pump has neither: two to fix.
    assert ana.get("/inventory/unset") == {"productPrices": 2}
    assert {p["sku"] for p in ana.get("/inventory/products", missing="true")} == {"PCM-500", "PUMP"}
    ana.patch(f"/inventory/products/{world['pcm']}", {"sellingPrice": 12000})
    assert ana.get("/inventory/unset") == {"productPrices": 1}
    # A service has no cost to set, only a price.
    ana.post("/inventory/products", {"sku": "SVC-1", "name": "Calibration", "productType": "service", "sellingPrice": 50000})
    assert ana.get("/inventory/unset") == {"productPrices": 1}
    # Switched off, it isn't on sale, so it doesn't count.
    ana.patch(f"/inventory/products/{world['pump']}", {"status": "inactive"})
    assert ana.get("/inventory/unset") == {}
    # The auditor can't price products, so nothing is theirs to see.
    ana.patch(f"/inventory/products/{world['pump']}", {"status": "active"})
    assert Api(client, people["aud"]).get("/inventory/unset") == {}
