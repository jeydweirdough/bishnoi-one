"""The sidebar's red counts: what isn't set up yet, for whoever can fix it."""

from .test_workflow import medicine


def test_a_medicine_with_no_price_is_counted_for_who_can_price_it(client, ana, cy):
    priced = medicine(client, ana)
    free = medicine(client, ana, code="PCM500", genericName="Paracetamol", price=0)
    assert client.get("/unset", headers=ana).json() == {"medicinePrices": 1}
    assert [m["id"] for m in client.get("/medicines?missing=true", headers=ana).json()] == [free["id"]]
    assert priced["id"] not in [m["id"] for m in client.get("/medicines?missing=true", headers=ana).json()]
    # Someone who can't change medicines isn't shown it.
    assert client.get("/unset", headers=cy).json() == {}
    r = client.patch(f"/medicines/{free['id']}", json={"priceCentavos": 900}, headers=ana)
    assert r.status_code == 200, r.text
    assert client.get("/unset", headers=ana).json() == {}
