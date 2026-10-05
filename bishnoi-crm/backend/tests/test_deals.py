"""Deals (D2): on a customer, through stages, won with a quote or lost with a
reason; the pipeline board and the forecast; and whose deals each role reaches."""

from datetime import date

from tests.test_customers import company, contact, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, errors, ids, line, save  # noqa: F401 (fixtures)

THIS_MONTH = date.today().isoformat()[:7]


def deal(client, headers, customer, name="Q4 order", **extra) -> dict:
    body = {"name": name, "companyId": customer["id"], "expectedCloseOn": date.today().isoformat(), **extra}
    r = client.post("/deals", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def names(client, headers, path="/deals") -> set[str]:
    return {d["name"] for d in client.get(path, headers=headers).json()["items"]}


def test_starting_stages_and_lists(client, ben):
    stages = client.get("/deal-stages", headers=ben).json()
    assert [(s["name"], s["outcome"], s["probability"], s["forecastCategory"]) for s in stages] == [
        ("Qualify", "open", 10, "pipeline"),
        ("Needs analysis", "open", 25, "pipeline"),
        ("Proposal", "open", 50, "best_case"),
        ("Negotiation", "open", 75, "commit"),
        ("Won", "won", 100, "closed"),
        ("Lost", "lost", 0, "omitted"),
    ]
    lists = client.get("/deal-lists", headers=ben).json()
    assert "Referral" in lists["sources"] and "Price" in lists["lostReasons"]


def test_a_deal_starts_in_the_first_stage_and_takes_its_forecast(client, ben):
    acme = company(client, ben)
    d = deal(client, ben, acme, valueCentavos=5_000_00, leadSource="Referral")
    assert (d["stage"]["code"], d["probability"], d["forecastCategory"], d["state"]) == ("qualify", 10, "pipeline", "open")
    assert (d["valueCentavos"], d["weightedCentavos"], d["leadSource"]) == (500000, 50000, "Referral")
    assert d["owner"]["name"] == "Ben Cruz" and d["can"]["edit"] and not d["can"]["delete"]  # a salesperson can't delete


def test_moving_stage_takes_the_stage_defaults_unless_given(client, ben):
    d = deal(client, ben, company(client, ben))
    moved = client.patch(f"/deals/{d['id']}", json={"stageCode": "proposal"}, headers=ben).json()
    assert (moved["probability"], moved["forecastCategory"]) == (50, "best_case")
    # The forecast category is the deal's own: a rep can commit ahead of the stage.
    own = client.patch(f"/deals/{d['id']}", json={"stageCode": "negotiation", "forecastCategory": "best_case", "probability": 60}, headers=ben).json()
    assert (own["stage"]["code"], own["probability"], own["forecastCategory"]) == ("negotiation", 60, "best_case")
    # Won and lost aren't stages to move to: they're closing.
    r = client.patch(f"/deals/{d['id']}", json={"stageCode": "won"}, headers=ben)
    assert r.status_code == 422 and errors(r) == {"stageCode": "Pick a stage from the list."}


def test_products_on_a_deal_are_priced_by_the_price_rules(client, crew, ids):
    acme = company(client, crew["ria"])
    d = deal(client, crew["ria"], acme, priceType="PATIENT", lines=[line(ids["AMX-500"], 2)], valueCentavos=1)
    assert d["valueCentavos"] == 2 * 145000  # the products' value, not the figure typed
    assert d["lines"][0]["productCode"] == "AMX-500" and d["lines"][0]["totalCentavos"] == 290000
    r = client.patch(f"/deals/{d['id']}", json={"valueCentavos": 5}, headers=crew["ria"])
    assert r.status_code == 422 and "products" in errors(r)["valueCentavos"]
    cleared = client.patch(f"/deals/{d['id']}", json={"lines": []}, headers=crew["ria"]).json()
    assert cleared["lines"] == [] and cleared["priceType"] is None
    r = client.post("/deals", json={"name": "x", "companyId": acme["id"], "expectedCloseOn": THIS_MONTH + "-01", "lines": [line(ids["AMX-500"])]}, headers=crew["ria"])
    assert r.status_code == 422 and "priceType" in errors(r)


def test_losing_needs_a_reason_from_the_list(client, ben):
    d = deal(client, ben, company(client, ben))
    r = client.post(f"/deals/{d['id']}/lose", json={"reason": "Bad vibes"}, headers=ben)
    assert r.status_code == 422 and errors(r) == {"reason": "Pick a reason from the list."}
    lost = client.post(f"/deals/{d['id']}/lose", json={"reason": "Went with a competitor", "competitor": "Rival Pharma"}, headers=ben).json()
    assert (lost["state"], lost["stage"]["code"], lost["probability"], lost["forecastCategory"]) == ("lost", "lost", 0, "omitted")
    assert (lost["lostReason"], lost["competitor"]) == ("Went with a competitor", "Rival Pharma") and lost["closedAt"]
    assert client.post(f"/deals/{d['id']}/win", json={}, headers=ben).status_code == 409  # closed: reopen first
    assert client.patch(f"/deals/{d['id']}", json={"stageCode": "qualify"}, headers=ben).status_code == 409
    back = client.post(f"/deals/{d['id']}/reopen", json={"stageCode": "proposal", "expectedCloseOn": "2026-12-15"}, headers=ben).json()
    assert (back["state"], back["stage"]["code"], back["lostReason"], back["closedAt"]) == ("open", "proposal", None, None)


def test_a_quote_made_for_the_deal_can_win_it(client, crew, ids):
    acme = company(client, crew["ria"])
    d = deal(client, crew["ria"], acme, valueCentavos=1_000_00)
    r = save(client, crew["ria"], acme, [line(ids["AMX-500"], 3)], dealId=d["id"])
    assert r.status_code == 201, r.text
    quote = r.json()
    assert quote["deal"] == {"id": d["id"], "name": "Q4 order"}
    assert [q["id"] for q in client.get(f"/deals/{d['id']}", headers=crew["ria"]).json()["quotes"]] == [quote["id"]]
    won = client.post(f"/deals/{d['id']}/win", json={"quoteId": quote["id"]}, headers=crew["ria"]).json()
    assert (won["state"], won["forecastCategory"], won["probability"]) == ("won", "closed", 100)
    assert (won["wonQuoteId"], won["valueCentavos"]) == (quote["id"], quote["totalCentavos"])
    assert won["expectedCloseOn"] == date.today().isoformat()  # counted when it closed


def test_a_quote_for_another_customers_deal_is_refused(client, crew, ids):
    acme, other = company(client, crew["ria"]), company(client, crew["ria"], "Other Co")
    d = deal(client, crew["ria"], other)
    r = save(client, crew["ria"], acme, [line(ids["AMX-500"])], dealId=d["id"])
    assert r.status_code == 422 and errors(r) == {"dealId": "Pick an open deal with this customer."}
    quote = save(client, crew["ria"], acme, [line(ids["AMX-500"])]).json()
    r = client.post(f"/deals/{d['id']}/win", json={"quoteId": quote["id"]}, headers=crew["ria"])
    assert r.status_code == 422 and "Other Co" in errors(r)["quoteId"]


def test_a_contact_must_be_with_the_deals_customer(client, ben):
    acme, other = company(client, ben), company(client, ben, "Other Co")
    maria = contact(client, ben, companyId=other["id"])
    r = client.post("/deals", json={"name": "x", "companyId": acme["id"], "contactId": maria["id"], "expectedCloseOn": "2026-12-01"}, headers=ben)
    assert r.status_code == 422 and errors(r) == {"contactId": "Maria isn't with Acme."}


def test_each_role_reaches_its_own_deals(client, crew):
    for who in ("ria", "rex", "sam"):
        deal(client, crew[who], company(client, crew[who], f"{who} co"), name=f"{who}'s deal")
    assert names(client, crew["ria"]) == {"ria's deal"}
    assert names(client, crew["lia"]) == {"ria's deal", "rex's deal"}  # her team
    assert names(client, crew["max"]) == {"ria's deal", "rex's deal", "sam's deal"}
    sams = next(d for d in client.get("/deals", headers=crew["max"]).json()["items"] if d["name"] == "sam's deal")
    assert client.get(f"/deals/{sams['id']}", headers=crew["ria"]).status_code == 404
    assert client.patch(f"/deals/{sams['id']}", json={"name": "mine"}, headers=crew["lia"]).status_code == 404


def test_the_board_groups_open_deals_by_stage(client, ben):
    acme = company(client, ben)
    deal(client, ben, acme, name="A", valueCentavos=100_00)
    b = deal(client, ben, acme, name="B", valueCentavos=300_00)
    client.patch(f"/deals/{b['id']}", json={"stageCode": "proposal"}, headers=ben)
    c = deal(client, ben, acme, name="C", valueCentavos=999_00)
    client.post(f"/deals/{c['id']}/lose", json={"reason": "Price"}, headers=ben)  # closed: not on the board
    columns = {col["stage"]["code"]: col for col in client.get("/deals-board", headers=ben).json()["columns"]}
    assert list(columns) == ["qualify", "needs", "proposal", "negotiation"]
    assert (columns["qualify"]["count"], columns["qualify"]["valueCentavos"], columns["qualify"]["weightedCentavos"]) == (1, 10000, 1000)
    assert (columns["proposal"]["count"], columns["proposal"]["weightedCentavos"]) == (1, 15000)
    assert columns["needs"]["deals"] == []


def test_the_forecast_adds_up_each_category_for_the_period(client, ben):
    acme = company(client, ben)
    deal(client, ben, acme, name="P", valueCentavos=100_00)  # pipeline, 10%
    deal(client, ben, acme, name="C", valueCentavos=200_00, stageCode="negotiation")  # commit, 75%
    deal(client, ben, acme, name="O", valueCentavos=900_00, forecastCategory="omitted")  # left out
    w = deal(client, ben, acme, name="W", valueCentavos=400_00)
    client.post(f"/deals/{w['id']}/win", json={}, headers=ben)
    deal(client, ben, acme, name="Later", valueCentavos=50_00, expectedCloseOn="2099-01-15")  # another period
    got = client.get(f"/deals-forecast?period={THIS_MONTH}", headers=ben).json()
    assert got["totals"] == {
        "pipelineCentavos": 10000,
        "bestCaseCentavos": 0,
        "commitCentavos": 20000,
        "wonCentavos": 40000,
        "weightedCentavos": 1000 + 15000,
        "deals": 3,
    }
    assert [p["owner"]["name"] for p in got["people"]] == ["Ben Cruz"]
    quarter = client.get("/deals-forecast?period=2099-Q1", headers=ben).json()
    assert (quarter["label"], quarter["totals"]["pipelineCentavos"]) == ("Q1 2099", 5000)
    assert client.get("/deals-forecast?period=2026-13", headers=ben).status_code == 422


def test_an_administrator_keeps_the_stages_and_lists(client, ana, ben):
    stages = client.post("/admin/deal-stages", json={"name": "Trial", "probability": 40, "forecastCategory": "best_case"}, headers=ana).json()
    assert [s["code"] for s in stages] == ["qualify", "needs", "proposal", "negotiation", "trial", "won", "lost"]
    assert client.post("/admin/deal-stages", json={"name": "Trial"}, headers=ben).status_code == 403
    # Won and lost can be renamed, nothing else; and they can't go.
    assert client.patch("/admin/deal-stages/won", json={"name": "Closed won"}, headers=ana).status_code == 200
    assert client.patch("/admin/deal-stages/won", json={"probability": 50}, headers=ana).status_code == 409
    assert client.delete("/admin/deal-stages/lost", headers=ana).status_code == 409
    # A stage in use can be switched off, not deleted.
    d = deal(client, ben, company(client, ben), stageCode="trial")
    assert d["probability"] == 40
    assert client.delete("/admin/deal-stages/trial", headers=ana).status_code == 409
    assert client.patch("/admin/deal-stages/trial", json={"isActive": False}, headers=ana).status_code == 200
    assert client.delete("/admin/deal-stages/needs", headers=ana).status_code == 204
    lists = client.put("/admin/deal-lists", json={"sources": ["Clinic event", "clinic event", "Referral"], "lostReasons": ["Price"]}, headers=ana).json()
    assert lists == {"sources": ["Clinic event", "Referral"], "lostReasons": ["Price"]}
    r = client.post("/deals", json={"name": "x", "companyId": d["company"]["id"], "expectedCloseOn": "2026-12-01", "leadSource": "Website"}, headers=ben)
    assert r.status_code == 422 and errors(r) == {"leadSource": "Pick a lead source from the list."}


def test_deleting_a_deal_keeps_its_quotes(client, crew, ids):
    acme = company(client, crew["lia"])
    d = deal(client, crew["lia"], acme)
    quote = save(client, crew["lia"], acme, [line(ids["AMX-500"])], dealId=d["id"]).json()
    assert client.delete(f"/deals/{d['id']}", headers=crew["lia"]).status_code == 204
    again = client.get(f"/quotes/{quote['id']}", headers=crew["lia"])
    assert again.status_code == 200 and again.json()["deal"] is None


# --- lead source on customers ---


def test_a_customer_has_a_lead_source_from_the_deals_list_and_deals_start_with_it(client, crew):
    from tests.conftest import bearer, sign_in

    ria = crew["ria"]
    acme = company(client, ria, "Acme", leadSource="Referral")
    assert acme["leadSource"] == "Referral"
    r = client.post("/companies", json={"name": "Beta", "leadSource": "Billboard"}, headers=ria)
    assert r.status_code == 422 and errors(r) == {"leadSource": "Pick a lead source from the list."}
    # A new deal starts with its customer's lead source, unless it's given one (or none).
    assert deal(client, ria, acme)["leadSource"] == "Referral"
    assert deal(client, ria, acme, leadSource="Event")["leadSource"] == "Event"
    assert deal(client, ria, acme, leadSource=None)["leadSource"] is None

    # On the customer form, its choices are the deals' list; one added there goes on that list.
    ana = bearer(sign_in(client))
    form = client.get("/forms/company", headers=ria).json()
    field = next(f for s in form["sections"] for f in s["fields"] if f["key"] == "leadSource")
    assert field["options"] == client.get("/deal-lists", headers=ria).json()["sources"] and field["sharedList"] is True
    assert client.post("/admin/forms/company/fields/leadSource/options", json={"label": "Trade show"}, headers=ana).status_code == 200
    assert "Trade show" in client.get("/deal-lists", headers=ria).json()["sources"]
    # The forms editor saves the form as it is, with no choices of its own for this field.
    editor = client.get("/forms/company?all=true", headers=ana).json()
    body = {"sections": [{"id": s["id"], "title": s["title"], "columns": s["columns"], "fields": [{"id": f["id"], "label": f["label"], "type": f["type"], "required": f["required"], "hidden": f["hidden"], "inList": f["inList"], "options": f["options"], "helpText": f["helpText"], "placeholder": f["placeholder"]} for f in s["fields"]]} for s in editor["sections"]]}
    assert client.put("/admin/forms/company", json=body, headers=ana).status_code == 200, "the form saves"
    assert client.patch(f"/companies/{acme['id']}", json={"leadSource": "Trade show"}, headers=ria).json()["leadSource"] == "Trade show"
