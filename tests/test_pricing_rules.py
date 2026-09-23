"""Settings -> Pricing rules: the agreed starting rules, and admins changing them."""

from app.seed import seed_reference
from tests.conftest import price_list_in


def rules(client, as_) -> dict:
    r = client.get("/admin/pricing", headers=as_("carmen"))
    assert r.status_code == 200, r.text
    return r.json()


def division(body: dict, code: str) -> dict:
    return next(d for d in body["divisions"] if d["code"] == code)


def test_the_starting_rules(client, as_):
    body = rules(client, as_)
    assert division(body, "b2c")["priceTypes"] == {"patient": "always", "srp": "always", "doctor": "with_rx"}
    assert division(body, "hos")["priceTypes"] == {
        "drugstore-hospital": "always", "patient": "always", "doctor": "always", "srp": "always"
    }
    assert division(body, "stc")["priceTypes"] == {"patient": "always", "doctor": "always", "srp": "always"}
    assert division(body, "b2b")["priceTypes"] == {"srp": "always", "distributor": "always"}
    assert division(body, "b2b")["allowsGuaranteeLetters"] is False
    assert all(division(body, d)["allowsGuaranteeLetters"] for d in ("b2c", "stc", "uro", "bnb", "hos", "bid"))
    assert division(body, "uro")["priceTypes"] == {} and division(body, "bnb")["priceTypes"] == {}
    assert division(body, "bid")["usesPriceList"] is False

    types = {t["code"]: t for t in body["priceTypes"]}
    assert types["special"] | {"requiresNotes": True, "needsApproval": True, "entry": "entered"} == types["special"]
    assert types["government"]["requiresNotes"] and types["government"]["needsApproval"]
    assert [i["name"] for i in body["issuers"]] == ["DSWD", "PCSO"]


def test_only_system_admins(client, as_):
    for who in ("ana", "joy", "iris", "ramon"):
        assert client.get("/admin/pricing", headers=as_(who)).status_code == 403


def uro(price_types: dict, **flags) -> dict:
    rules = {"usesPriceList": True, "allowsGuaranteeLetters": True, "discountApprovalBp": 500, "priceTypes": price_types}
    return {"divisions": {"uro": rules | flags}}


def test_admins_set_a_divisions_prices(client, as_):
    carmen = as_("carmen")
    r = client.put("/admin/pricing/divisions", json=uro({"patient": "always", "special": "always"}), headers=carmen)
    assert r.status_code == 200 and division(r.json(), "uro")["discountApprovalBp"] == 500
    price_list = price_list_in(client, as_("ramon"), "uro")
    assert {t["code"] for t in price_list["priceTypes"]} == {"patient", "special"}

    assert client.put("/admin/pricing/divisions", json=uro({"doctor": "with_rx"}), headers=carmen).status_code == 422
    assert client.put("/admin/pricing/divisions", json=uro({"nope": "always"}), headers=carmen).status_code == 422
    finance = {"divisions": {"finance": uro({})["divisions"]["uro"]}}
    assert client.put("/admin/pricing/divisions", json=finance, headers=carmen).status_code == 422


def test_admin_changes_survive_seeding_again(app, client, as_):
    b2c = {"usesPriceList": True, "allowsGuaranteeLetters": True, "discountApprovalBp": 1000, "priceTypes": {"patient": "always"}}
    assert client.put("/admin/pricing/divisions", json={"divisions": {"b2c": b2c}}, headers=as_("carmen")).status_code == 200
    with app.state.sessions() as db:
        seed_reference(db)
    assert division(rules(client, as_), "b2c")["priceTypes"] == {"patient": "always"}


def test_price_types_and_issuers(client, as_):
    carmen, ana = as_("carmen"), as_("ana")
    r = client.post("/admin/pricing/price-types", json={"name": "Senior Citizen Price"}, headers=carmen)
    assert r.status_code == 201 and "senior-citizen-price" in {t["code"] for t in r.json()["priceTypes"]}
    assert client.post("/admin/pricing/price-types", json={"name": "senior citizen price"}, headers=carmen).status_code == 409

    b2c = {"usesPriceList": True, "allowsGuaranteeLetters": True, "discountApprovalBp": 1000,
           "priceTypes": {"patient": "always", "special": "always"}}
    client.put("/admin/pricing/divisions", json={"divisions": {"b2c": b2c}}, headers=carmen)
    codes = lambda: {t["code"] for t in price_list_in(client, ana, "b2c")["priceTypes"]}  # noqa: E731
    assert codes() == {"patient", "special"}
    assert client.patch("/admin/pricing/price-types/special", json={"isActive": False}, headers=carmen).status_code == 200
    assert codes() == {"patient"}

    r = client.post("/admin/pricing/issuers", json={"name": "Malasakit Center"}, headers=carmen)
    assert r.status_code == 201
    issuers = lambda: [i["name"] for i in price_list_in(client, ana, "b2c")["issuers"]]  # noqa: E731
    assert issuers() == ["DSWD", "PCSO", "Malasakit Center"]
    client.patch("/admin/pricing/issuers/pcso", json={"isActive": False}, headers=carmen)
    assert issuers() == ["DSWD", "Malasakit Center"]
