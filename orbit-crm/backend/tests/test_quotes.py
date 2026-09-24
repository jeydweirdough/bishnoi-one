"""The catalogue, team prices, and quotes: pricing, guarantee letters, and the
approver's decisions."""

import json

import pytest
from sqlalchemy import func, select

from app.models import StoredFile
from app.tools.users import make_demo_catalogue
from tests.test_customers import company, contact, crew  # noqa: F401 (crew is a fixture)

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def catalogue(app) -> None:
    with app.state.sessions() as db:
        make_demo_catalogue(db)


@pytest.fixture
def ids(client, crew, catalogue) -> dict[str, str]:  # noqa: F811
    """Product and bundle ids by code."""
    products = client.get("/products", headers=crew["max"]).json()["items"]
    bundles = client.get("/bundles", headers=crew["max"]).json()["items"]
    promos = client.get("/promos", headers=crew["max"]).json()["items"]
    return {p["code"]: p["id"] for p in products} | {b["code"]: b["id"] for b in bundles} | {p["name"]: p["id"] for p in promos}


def line(product_id, quantity=1, **extra) -> dict:
    return {"productId": product_id, "quantity": quantity, **extra}


def preview(client, headers, customer, lines, price_type="PATIENT", kind="companies", **extra):
    return client.post(f"/{kind}/{customer['id']}/quotes/preview", json={"priceType": price_type, "lines": lines, **extra}, headers=headers)


def save(client, headers, customer, lines, price_type="PATIENT", kind="companies", letter_file=None, **extra):
    body = {"priceType": price_type, "lines": lines, **extra}
    files = {"letterFile": ("letter.pdf", letter_file, "application/pdf")} if letter_file is not None else None
    return client.post(f"/{kind}/{customer['id']}/quotes", data={"quote": json.dumps(body)}, files=files, headers=headers)


def errors(r) -> dict[str, str]:
    return {".".join(str(p) for p in e["loc"][1:]): e["msg"] for e in r.json()["detail"]}


# --- the price list and pricing ---


def test_price_list_offers_the_catalogue(client, crew, ids):
    acme = company(client, crew["ria"])
    r = client.get(f"/companies/{acme['id']}/price-list", headers=crew["ria"])
    assert r.status_code == 200, r.text
    got = r.json()
    assert [t["code"] for t in got["priceTypes"]] == ["PATIENT", "TRADE", "DOCTOR", "SPECIAL"]
    amox = next(p for p in got["products"] if p["code"] == "AMX-500")
    assert amox["prices"] == {"PATIENT": 145000, "TRADE": 118000, "DOCTOR": 130000}
    assert {i["code"] for i in got["issuers"]} == {"DSWD", "PCSO", "MAYOR"}
    assert len(got["promos"]) == 3 and len(got["bundles"]) == 2


def test_lines_are_priced_with_promos_and_discounts(client, crew, ids):
    acme = company(client, crew["ria"])
    r = preview(
        client,
        crew["ria"],
        acme,
        [
            line(ids["CTZ-10"], 2, promoId=ids["Flu season 10% off"]),  # 2 × 980 = 1,960, 10% off
            line(ids["AMX-500"], 21, promoId=ids["Buy 10, get 1"]),  # 2 free
            line(ids["VTC-500"], 50, promoId=ids["Volume discount"]),  # the 5% tier
            line(ids["ORS-SACH"], 1, discount={"kind": "amount", "value": 1000}),  # 10.00 off 310.00
        ],
    )
    assert r.status_code == 200, r.text
    lines = r.json()["lines"]
    assert (lines[0]["grossCentavos"], lines[0]["promoDiscountCentavos"], lines[0]["totalCentavos"]) == (196000, 19600, 176400)
    assert (lines[1]["freeQuantity"], lines[1]["totalCentavos"]) == (2, 21 * 145000)
    assert lines[2]["promoDiscountCentavos"] == 50 * 72000 * 5 // 100
    assert (lines[3]["discountCentavos"], lines[3]["totalCentavos"]) == (1000, 30000)
    got = r.json()
    assert got["totalCentavos"] == sum(x["totalCentavos"] for x in lines)
    assert got["approvalReasons"] == []  # 10.00 off 310.00 is under 10%


def test_big_discounts_and_some_price_types_need_approval(client, crew, ids):
    acme = company(client, crew["ria"])
    r = preview(client, crew["ria"], acme, [line(ids["ORS-SACH"], 1, discount={"kind": "percent", "value": 1500})])
    assert r.json()["approvalReasons"] == ["discount"]
    r = preview(client, crew["ria"], acme, [line(ids["ORS-SACH"], 1, unitPriceCentavos=20000)], price_type="SPECIAL")
    assert (r.json()["approvalReasons"], r.json()["totalCentavos"]) == (["price"], 20000)
    r = preview(client, crew["ria"], acme, [line(ids["ORS-SACH"], 1)], price_type="SPECIAL")
    assert "lines.0.unitPriceCentavos" in errors(r)


def test_prescription_prices_follow_the_rx(client, crew, ids):
    acme = company(client, crew["ria"])
    assert "priceType" in errors(preview(client, crew["ria"], acme, [line(ids["AMX-500"])], price_type="DOCTOR"))
    assert "priceType" in errors(preview(client, crew["ria"], acme, [line(ids["AMX-500"])], rx=True))
    r = preview(client, crew["ria"], acme, [line(ids["AMX-500"])], price_type="DOCTOR", rx=True)
    assert r.json()["totalCentavos"] == 130000


def test_a_promo_must_apply_to_the_product(client, crew, ids):
    acme = company(client, crew["ria"])
    r = preview(client, crew["ria"], acme, [line(ids["ALP-5"], 1, promoId=ids["Flu season 10% off"])])
    assert "lines.0.promoId" in errors(r)


def test_bundles_come_to_their_set_price(client, crew, ids):
    acme = company(client, crew["ria"])
    one = preview(client, crew["ria"], acme, [{"bundleId": ids["KIDS-KIT"], "quantity": 2}]).json()
    assert len(one["lines"]) == 1 and one["totalCentavos"] == 180000
    assert one["grossCentavos"] == 2 * (4 * 16500 + 31000)  # what the items would have cost
    trio = preview(client, crew["ria"], acme, [{"bundleId": ids["MAINT-3"], "quantity": 1}]).json()
    assert len(trio["lines"]) == 3 and trio["totalCentavos"] == 420000
    assert all(x["bundleId"] == ids["MAINT-3"] for x in trio["lines"])


# --- saving, reach, and the approver ---


def test_a_quote_is_saved_numbered_and_seen_by_whoever_reaches_it(client, crew, ids):
    acme = company(client, crew["ria"])
    r = save(client, crew["ria"], acme, [line(ids["AMX-500"], 2)])
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["number"].startswith("Q-") and q["number"].endswith("-0001")
    assert (q["state"], q["totalCentavos"], q["customerHref"]) == ("ready", 290000, f"/companies/{acme['id']}")
    assert client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["total"] == 1
    assert client.get(f"/quotes/{q['id']}", headers=crew["lia"]).status_code == 200  # her team's
    assert client.get(f"/quotes/{q['id']}", headers=crew["sam"]).status_code == 404  # not his
    assert client.get("/quotes", headers=crew["sam"]).json()["total"] == 0
    assert save(client, crew["ria"], acme, [line(ids["AMX-500"])]).json()["number"].endswith("-0002")


def test_a_contacts_quote_shows_on_its_company_too(client, crew, ids):
    acme = company(client, crew["ria"])
    maria = contact(client, crew["ria"], companyId=acme["id"])
    q = save(client, crew["ria"], maria, [line(ids["AMX-500"])], kind="contacts").json()
    assert q["customerName"] == "Maria, Acme" and q["contact"]["id"] == maria["id"]
    assert client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["total"] == 1


def test_special_prices_need_notes_and_approval(client, crew, ids):
    acme = company(client, crew["ria"])
    r = save(client, crew["ria"], acme, [line(ids["AMX-500"], 1, unitPriceCentavos=100000)], price_type="SPECIAL")
    assert "notes" in errors(r)
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 1, unitPriceCentavos=100000)], price_type="SPECIAL", notes="Hospital tender").json()
    assert (q["state"], q["approval"]["status"], q["can"]["approve"]) == ("waiting", "pending", False)
    assert client.post(f"/quotes/{q['id']}/approval", json={"decision": "approve"}, headers=crew["ria"]).status_code == 403
    assert client.post(f"/quotes/{q['id']}/approval", json={"decision": "reject"}, headers=crew["max"]).status_code == 422  # needs a reason
    r = client.post(f"/quotes/{q['id']}/approval", json={"decision": "reject", "note": "Too low"}, headers=crew["max"])
    assert (r.json()["state"], r.json()["approval"]["note"], r.json()["approval"]["by"]["name"]) == ("rejected", "Too low", "Max")
    assert client.post(f"/quotes/{q['id']}/approval", json={"decision": "approve"}, headers=crew["max"]).status_code == 409


def test_a_guarantee_letter_is_checked_then_paid(client, crew, ids):
    acme = company(client, crew["ria"])
    letter = {"number": "GL-77", "issuedOn": "2026-01-15", "amountCentavos": 200000}
    lines = [line(ids["AMX-500"], 2)]
    assert "letterFile" in errors(save(client, crew["ria"], acme, lines, payer="DSWD", letter=letter))
    assert "letterFile" in errors(save(client, crew["ria"], acme, lines, payer="DSWD", letter=letter, letter_file=b"not a pdf"))
    assert "payer" in errors(save(client, crew["ria"], acme, lines, payer="NOBODY", letter=letter, letter_file=PDF))
    r = save(client, crew["ria"], acme, lines, payer="DSWD", letter=letter, letter_file=PDF)
    assert r.status_code == 201, r.text
    q = r.json()
    assert (q["state"], q["payerName"], q["letter"]["status"], q["payment"]["status"]) == ("waiting", "DSWD", "pending", "unpaid")
    got = client.get(f"/quotes/{q['id']}/letter", headers=crew["ria"])
    assert (got.status_code, got.content, got.headers["content-type"]) == (200, PDF, "application/pdf")
    assert client.get(f"/quotes/{q['id']}/letter", headers=crew["sam"]).status_code == 404

    assert client.post(f"/quotes/{q['id']}/payments", json={"paidOn": "2026-02-01"}, headers=crew["max"]).status_code == 409  # not verified yet
    q = client.post(f"/quotes/{q['id']}/letter-check", json={"decision": "approve"}, headers=crew["max"]).json()
    assert (q["state"], q["can"]["recordPayment"]) == ("ready", True)
    pay = lambda body: client.post(f"/quotes/{q['id']}/payments", json=body, headers=crew["max"])  # noqa: E731
    assert "amountCentavos" in errors(pay({"paidOn": "2026-02-01", "amountCentavos": 999999}))
    assert pay({"paidOn": "2026-02-01", "amountCentavos": 50000, "reference": "OR-1"}).json()["payment"]["status"] == "partial"
    done = pay({"paidOn": "2026-02-02"}).json()  # the rest
    assert (done["payment"]["status"], done["payment"]["paidCentavos"], done["can"]["delete"]) == ("paid", 200000, False)
    assert client.delete(f"/quotes/{q['id']}", headers=crew["max"]).status_code == 409  # paid: it stays


def test_deleting_a_quote_removes_its_letter(app, client, crew, ids):
    acme = company(client, crew["ria"])
    letter = {"number": "GL-1", "issuedOn": "2026-01-15", "amountCentavos": 100000}
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"])], payer="PCSO", letter=letter, letter_file=PDF).json()
    def letters() -> int:
        with app.state.sessions() as db:
            return db.scalar(select(func.count()).select_from(StoredFile))

    assert letters() == 1
    letter_file = client.get(f"/quotes/{q['id']}/letter", headers=crew["ria"])
    assert (letter_file.status_code, letter_file.content, letter_file.headers["content-type"]) == (200, PDF, "application/pdf")
    assert client.delete(f"/quotes/{q['id']}", headers=crew["ria"]).status_code == 403  # reps don't delete quotes
    assert client.delete(f"/quotes/{q['id']}", headers=crew["lia"]).status_code == 204
    assert letters() == 0
    assert client.get(f"/quotes/{q['id']}", headers=crew["lia"]).status_code == 404


def test_approver_lists(client, crew, ids):
    acme = company(client, crew["ria"])
    save(client, crew["ria"], acme, [line(ids["AMX-500"], 1, unitPriceCentavos=1000)], price_type="SPECIAL", notes="Why")
    save(client, crew["ria"], acme, [line(ids["AMX-500"])])
    assert client.get("/quotes?task=approvals", headers=crew["max"]).json()["total"] == 1
    assert client.get("/quotes?state=ready", headers=crew["max"]).json()["total"] == 1


# --- team prices ---


def test_a_team_lead_sets_their_teams_prices(client, crew, ids):
    ria_co = company(client, crew["ria"], "Ria Co")
    sam_co = company(client, crew["sam"], "Sam Co")
    assert client.get("/prices/teams", headers=crew["ria"]).status_code == 403  # reps don't
    teams = client.get("/prices/teams", headers=crew["lia"]).json()
    assert [t["name"] for t in teams] == ["North"]  # only her own
    north = teams[0]["id"]
    south = next(t["id"] for t in client.get("/prices/teams", headers=crew["max"]).json() if t["name"] == "South")
    assert client.get(f"/prices?team={south}", headers=crew["lia"]).status_code == 404

    r = client.put(f"/prices?team={north}", json={"items": [{"productId": ids["AMX-500"], "priceTypeCode": "PATIENT", "amountCentavos": 140000}]}, headers=crew["lia"])
    assert r.status_code == 200, r.text
    cell = next(p for p in r.json()["products"] if p["code"] == "AMX-500")["prices"]["PATIENT"]
    assert cell == {"company": 145000, "team": 140000}
    assert preview(client, crew["ria"], ria_co, [line(ids["AMX-500"])]).json()["totalCentavos"] == 140000
    assert preview(client, crew["sam"], sam_co, [line(ids["AMX-500"])]).json()["totalCentavos"] == 145000

    sheet = client.put(f"/prices/types?team={north}", json={"codes": ["TRADE"]}, headers=crew["lia"]).json()
    assert sheet["usesAllTypes"] is False
    offered = client.get(f"/companies/{ria_co['id']}/price-list", headers=crew["ria"]).json()["priceTypes"]
    assert [t["code"] for t in offered] == ["TRADE"]
    # Cleared: back to the company's price.
    client.put(f"/prices?team={north}", json={"items": [{"productId": ids["AMX-500"], "priceTypeCode": "PATIENT", "amountCentavos": None}]}, headers=crew["lia"])
    assert client.put(f"/prices/types?team={north}", json={"codes": []}, headers=crew["lia"]).json()["usesAllTypes"] is True
    assert preview(client, crew["ria"], ria_co, [line(ids["AMX-500"])]).json()["totalCentavos"] == 145000


# --- the catalogue ---


def test_products_are_kept_by_those_allowed(client, crew, ana, catalogue):
    body = {"code": "new-1", "name": "Newcillin", "unit": "box", "prices": {"PATIENT": 5000, "TRADE": 4000}}
    assert client.post("/products", json=body, headers=crew["ria"]).status_code == 403
    r = client.post("/products", json=body, headers=ana)
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["code"], p["prices"]) == ("NEW-1", {"PATIENT": 5000, "TRADE": 4000})
    assert "code" in errors(client.post("/products", json=body, headers=ana))
    p = client.patch(f"/products/{p['id']}", json={"prices": {"TRADE": None, "DOCTOR": 4500}}, headers=ana).json()
    assert p["prices"] == {"PATIENT": 5000, "DOCTOR": 4500}
    assert client.get("/products?q=newc", headers=crew["ria"]).json()["total"] == 1
    assert client.delete(f"/products/{p['id']}", headers=ana).status_code == 204


def test_a_product_in_a_bundle_stays(client, ana, ids):
    assert client.delete(f"/products/{ids['PCM-SYR']}", headers=ana).status_code == 409


def test_promos_and_bundles_are_checked(client, ana, ids):
    assert client.post("/promos", json={"name": "Half off", "kind": "percent"}, headers=ana).status_code == 422
    r = client.post("/promos", json={"name": "Half off", "kind": "percent", "percentBp": 5000, "startsOn": "2099-01-01"}, headers=ana)
    assert r.status_code == 201 and r.json()["state"] == "upcoming"
    r = client.post("/promos", json={"name": "Old", "kind": "amount", "amountCentavos": 100, "startsOn": "2025-02-01", "endsOn": "2025-01-01"}, headers=ana)
    assert "endsOn" in errors(r)
    bundle = {"code": "duo", "name": "Duo", "priceCentavos": 1000, "items": [{"productId": ids["AMX-500"], "qty": 1}, {"productId": ids["AMX-500"], "qty": 2}]}
    assert "items" in errors(client.post("/bundles", json=bundle, headers=ana))


def test_the_rules_can_be_changed(client, ana, crew, catalogue):
    rules = client.patch("/pricing/settings", json={"discountApprovalBp": 2000}, headers=ana).json()
    assert rules["settings"]["discountApprovalBp"] == 2000
    assert "lostDays" in errors(client.patch("/pricing/settings", json={"lostDays": 10}, headers=ana))
    rules = client.patch("/pricing/price-types/SPECIAL", json={"isActive": False}, headers=ana).json()
    assert next(t for t in rules["priceTypes"] if t["code"] == "SPECIAL")["isActive"] is False
    assert client.patch("/pricing/settings", json={"lostDays": 200}, headers=crew["lia"]).status_code == 403


def test_a_requested_price_goes_to_the_salespersons_team_lead(app, client, crew, ids):
    """A salesperson asks for a lower price for a client; their own lead approves it."""
    from app.models import Team, User
    from app.security import hash_password
    from tests.conftest import PASSWORD, bearer, role_id, sign_in

    with app.state.sessions() as db:  # a lead for South too, who mustn't see North's quotes
        south = db.query(Team).filter_by(name="South").one()
        db.add(User(email="lou@example.com", full_name="Lou", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Team Lead"), team_id=south.id))
        db.commit()
    lou = bearer(sign_in(client, "lou@example.com"))
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 10, unitPriceCentavos=120000)], price_type="SPECIAL", notes="Client asked for a lower price").json()
    assert (q["state"], q["approval"]["reasons"]) == ("waiting", ["price"])
    assert client.get("/quotes?task=approvals", headers=crew["lia"]).json()["total"] == 1  # Ria's lead sees it
    assert client.get("/quotes?task=approvals", headers=lou).json()["total"] == 0  # another team's lead doesn't
    assert client.post(f"/quotes/{q['id']}/approval", json={"decision": "approve"}, headers=lou).status_code == 404
    done = client.post(f"/quotes/{q['id']}/approval", json={"decision": "approve"}, headers=crew["lia"]).json()
    assert (done["state"], done["approval"]["by"]["name"]) == ("ready", "Lia")
