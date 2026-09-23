"""Quotes in the sales workspace: each division's pricing rules, guarantee
letters, and quotes moving and going with their customer."""

from tests.conftest import PDF, customer_id, field_messages, post_quote, preview_quote, price_list_in, product_ids

BNB_SRP = {
    "divisions": {
        "bnb": {"usesPriceList": True, "allowsGuaranteeLetters": True, "discountApprovalBp": 1000, "priceTypes": {"srp": "always"}}
    }
}


def test_the_price_list_has_only_the_divisions_prices(client, as_):
    b2c = price_list_in(client, as_("ana"), "b2c")
    assert {t["code"]: t["rule"] for t in b2c["priceTypes"]} == {"srp": "always", "patient": "always", "doctor": "with_rx"}
    assert all(set(p["prices"]) <= {"srp", "patient", "doctor"} for p in b2c["products"])
    assert b2c["allowsGuaranteeLetters"] and [i["name"] for i in b2c["issuers"]] == ["DSWD", "PCSO"]
    assert {p["name"] for p in b2c["promos"]} == {"Vitamin C 10% off", "₱10 off Paracetamol Syrup"}

    b2b = price_list_in(client, as_("ramon"), "b2b")
    assert {t["code"] for t in b2b["priceTypes"]} == {"srp", "distributor"}
    assert b2b["allowsGuaranteeLetters"] is False and b2b["issuers"] == []


def test_a_price_list_needs_a_customer_you_can_see(client, as_):
    """Grace sells in HOS. A B2C customer is simply not found for her, which
    tells her nothing about who B2C sells to."""
    maria = customer_id(client, as_("ana"), "b2c", "Maria Lopez")
    assert client.get(f"/sales/customers/{maria}/price-list", headers=as_("grace")).status_code == 404


def test_a_quote_paid_with_a_dswd_letter(client, as_):
    ana = as_("ana")
    maria = customer_id(client, ana, "b2c", "Maria Lopez")
    ids = product_ids(client, ana, "b2c")
    quote = {
        "priceType": "patient",
        "payer": "dswd",
        "lines": [{"productId": ids["ASC-500"], "quantity": 2}],
        "letter": {"number": "DSWD-1", "issuedOn": "2026-09-10", "amountCentavos": 96000},
    }
    r = post_quote(client, ana, "b2c", maria, quote)
    assert r.status_code == 422
    assert field_messages(r) == {"letterFile": "Attach the guarantee letter: a PDF, or a photo (JPG or PNG)."}
    r = post_quote(client, ana, "b2c", maria, quote, letter=b"MZ not a letter at all")
    assert field_messages(r) == {"letterFile": "Attach a PDF, JPG or PNG file."}

    r = post_quote(client, ana, "b2c", maria, quote, letter=PDF)
    assert r.status_code == 201, r.text
    q = r.json()
    assert (q["totalCentavos"], q["state"], q["payerName"]) == (96000, "waiting", "DSWD")
    assert q["letter"]["status"] == "pending" and q["letter"]["file"]["contentType"] == "application/pdf"
    assert q["payment"]["status"] == "unpaid"

    letter = client.get(f"/sales/quotes/{q['id']}/letter", headers=ana)
    assert letter.status_code == 200 and letter.content == PDF
    assert letter.headers["content-type"] == "application/pdf"

    detail = client.get(f"/sales/customers/{maria}", headers=ana).json()
    assert [x["number"] for x in detail["quotes"]] == [q["number"]]
    # Ben works B2C / MD Telesales; Maria is in B2C / General.
    assert client.get(f"/sales/quotes/{q['id']}", headers=as_("ben")).status_code == 404
    assert client.get(f"/sales/quotes/{q['id']}/letter", headers=as_("ben")).status_code == 404


def test_the_divisions_rules_are_enforced(client, as_):
    ana = as_("ana")
    maria = customer_id(client, ana, "b2c", "Maria Lopez")
    line = [{"productId": product_ids(client, ana, "b2c")["MET-500"], "quantity": 1}]
    r = post_quote(client, ana, "b2c", maria, {"priceType": "distributor", "lines": line})
    assert field_messages(r) == {"priceType": "Pick one of this division's prices."}
    r = post_quote(client, ana, "b2c", maria, {"priceType": "patient", "rx": True, "lines": line})
    assert field_messages(r) == {"priceType": "With an Rx, use Doctor's Price."}
    r = post_quote(client, ana, "b2c", maria, {"priceType": "doctor", "rx": True, "lines": line})
    assert r.status_code == 201 and (r.json()["totalCentavos"], r.json()["state"]) == (65000, "ready")


def test_b2b_takes_no_guarantee_letters(client, as_):
    carmen = as_("carmen")
    ana_id = next(u["id"] for u in client.get("/admin/users", headers=carmen).json() if u["email"] == "ana@pharmacrm.test")
    grant = {"roleKey": "rep", "moduleKey": "b2b", "divisionCode": "b2b", "subdivisionCode": "nbd"}
    assert client.post(f"/admin/users/{ana_id}/assignments", json=grant, headers=carmen).status_code == 201

    ana = as_("ana")
    northpoint = customer_id(client, ana, "b2b", "Northpoint Distributors")
    quote = {
        "priceType": "distributor",
        "payer": "pcso",
        "lines": [{"productId": product_ids(client, ana, "b2b")["AMOX-500"], "quantity": 10}],
        "letter": {"number": "PCSO-1", "issuedOn": "2026-09-10", "amountCentavos": 980000},
    }
    r = post_quote(client, ana, "b2b", northpoint, quote, letter=PDF)
    assert field_messages(r) == {"payer": "This division doesn't take guarantee letters."}
    r = post_quote(client, ana, "b2b", northpoint, {**quote, "payer": "self", "letter": None})
    assert r.status_code == 201 and r.json()["totalCentavos"] == 980000


def test_a_preview_prices_without_saving(client, as_):
    ana = as_("ana")
    price_list = price_list_in(client, ana, "b2c")
    syrup = next(p["id"] for p in price_list["products"] if p["code"] == "PARA-SYR")
    promo = next(p["id"] for p in price_list["promos"] if p["name"] == "₱10 off Paracetamol Syrup")
    body = {"priceType": "patient", "payer": "dswd", "lines": [{"productId": syrup, "quantity": 3, "promoId": promo}]}
    maria = customer_id(client, ana, "b2c", "Maria Lopez")
    r = preview_quote(client, ana, maria, body)
    assert r.status_code == 200, r.text
    assert (r.json()["grossCentavos"], r.json()["totalCentavos"]) == (26700, 23700)
    assert client.get(f"/sales/customers/{maria}", headers=ana).json()["quotes"] == []


def test_quotes_move_and_go_with_their_customer(client, as_, files):
    assert client.put("/admin/pricing/divisions", json=BNB_SRP, headers=as_("carmen")).status_code == 200
    lorna = as_("lorna")
    noel = customer_id(client, lorna, "bnb", "Dr. Noel Tan")
    quote = {
        "priceType": "srp",
        "payer": "pcso",
        "lines": [{"productId": product_ids(client, lorna, "bnb")["MET-500"], "quantity": 1}],
        "letter": {"number": "PCSO-9", "issuedOn": "2026-09-01", "amountCentavos": 78000},
    }
    q = post_quote(client, lorna, "bnb", noel, quote, letter=PDF).json()
    assert len(files._memory) == 1

    rev = client.get(f"/sales/customers/{noel}", headers=lorna).json()["rev"]
    assert client.patch(f"/sales/customers/{noel}", json={"team": "md-telesales", "rev": rev}, headers=lorna).status_code == 200
    assert client.get(f"/sales/quotes/{q['id']}", headers=lorna).json()["team"] == "md-telesales"
    # Now in Paolo's team, so he sees it too.
    assert client.get(f"/sales/quotes/{q['id']}", headers=as_("paolo")).status_code == 200

    assert client.delete(f"/sales/customers/{noel}", headers=lorna).status_code == 204
    assert client.get(f"/sales/quotes/{q['id']}", headers=lorna).status_code == 404
    assert files._memory == {}


def test_who_can_delete_a_quote(client, as_, files):
    assert client.put("/admin/pricing/divisions", json=BNB_SRP, headers=as_("carmen")).status_code == 200
    paolo = as_("paolo")
    alma = customer_id(client, paolo, "bnb", "Dr. Alma Dizon")
    line = {"productId": product_ids(client, paolo, "bnb")["PARA-SYR"], "quantity": 10, "discount": {"kind": "percent", "value": 2000}}
    q = post_quote(client, paolo, "bnb", alma, {"priceType": "srp", "lines": [line]}).json()
    assert q["approval"] == {**q["approval"], "status": "pending", "reasons": ["discount"]}
    assert q["can"]["delete"] is True

    assert client.delete(f"/sales/quotes/{q['id']}", headers=as_("ana")).status_code == 403  # reps can't delete
    assert client.post(f"/finance/quotes/{q['id']}/approval", json={"decision": "approve"}, headers=as_("joy")).status_code == 200
    r = client.delete(f"/sales/quotes/{q['id']}", headers=paolo)
    assert r.status_code == 409  # Finance acted: it stays on record
    assert client.get(f"/sales/quotes/{q['id']}", headers=paolo).json()["can"]["delete"] is False

    other = post_quote(client, paolo, "bnb", alma, {"priceType": "srp", "lines": [{**line, "discount": None}]}).json()
    assert client.delete(f"/sales/quotes/{other['id']}", headers=paolo).status_code == 204
