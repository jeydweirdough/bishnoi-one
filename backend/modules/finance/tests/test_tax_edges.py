"""Tax: what the registration and a sale refuse, each on the field it's about."""

from .test_tax_api import REGISTRATION, app, ana, ben, client, line  # noqa: F401 (fixtures)


def field(response) -> str:
    assert response.status_code == 422, response.text
    return response.json()["detail"][0]["loc"][-1]


def test_the_registration_refuses_what_a_bir_form_would(client, ana):
    assert field(client.put("/tax/profile", json={**REGISTRATION, "country": "XX"}, headers=ana)) == "country"
    assert field(client.put("/tax/profile", json={**REGISTRATION, "regime": "exempt"}, headers=ana)) == "regime"
    assert field(client.put("/tax/profile", json={**REGISTRATION, "tin": "123-456-789", "branchCode": "12"}, headers=ana)) == "branchCode"
    # The branch code can come with the TIN, and a 3-digit one is kept as given.
    profile = client.put("/tax/profile", json={**REGISTRATION, "tin": "123-456-789-001"}, headers=ana).json()["profile"]
    assert (profile["tin"], profile["branchCode"]) == ("123-456-789", "001")


def test_a_sale_refuses_what_its_invoice_could_not_show(client, ben):
    assert field(client.post("/tax/compute", json={"treatment": "tourist", "lines": [line(100)]}, headers=ben)) == "treatment"
    assert field(client.post("/tax/compute", json={"lines": [line(100, category="luxury")]}, headers=ben)) == "category"
    assert field(client.post("/tax/compute", json={"buyer": {"tin": "12"}, "lines": [line(100)]}, headers=ben)) == "tin"
    assert client.post("/tax/compute", json={"lines": []}, headers=ben).status_code == 422
