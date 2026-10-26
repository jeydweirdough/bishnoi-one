"""The order of work: received -> checked -> verified -> dispensed from a batch -> sold.

Checking comes before dispensing, and only a verified prescription can be
dispensed; only an eligible batch can be picked; a prescription medicine
can't be sold over the counter.
"""

from datetime import date, timedelta

import pytest

from app.models import CHECK_KEYS, Batch

ALL_TICKED = {k: True for k in CHECK_KEYS}
TODAY = date.today()


def medicine(client, headers, code="AMX500", rx_class="rx", price=1250, **extra) -> dict:
    r = client.post("/medicines", headers=headers, json={
        "code": code, "genericName": extra.pop("genericName", "Amoxicillin"), "strength": "500 mg", "dosageForm": "capsule",
        "unit": "capsule", "rxClass": rx_class, "priceCentavos": price, "reorderLevel": 10, **extra,
    })
    assert r.status_code == 201, r.text
    return r.json()


def receive(client, headers, lines: list[dict]) -> dict:
    r = client.post("/stock/receivings", headers=headers, json={"receivedOn": TODAY.isoformat(), "reference": "INV-1", "lines": lines})
    assert r.status_code == 201, r.text
    return r.json()


def lot(medicine_id: str, lot_no: str, days: int, qty: int) -> dict:
    return {"medicineId": medicine_id, "lotNo": lot_no, "expiresOn": (TODAY + timedelta(days=days)).isoformat(), "quantity": qty, "costCentavos": 700}


def take_in(client, headers, medicine_id: str | None = None, qty: int = 21, **extra) -> dict:
    r = client.post("/prescriptions", headers=headers, json={
        "newPatient": {"fullName": "Juan Dela Cruz", "birthDate": "1968-03-14"},
        "prescriberName": "Dr. Elena Ramos",
        "prescriberLicense": extra.pop("prescriberLicense", "PRC-0112233"),
        "prescribedOn": extra.pop("prescribedOn", TODAY.isoformat()),
        "items": [{"writtenAs": "Amoxicillin 500mg cap", "medicineId": medicine_id, "quantity": qty, "directions": "1 cap 3x a day"}],
        **extra,
    })
    assert r.status_code == 201, r.text
    return r.json()


def verify(client, headers, rx: dict, medicine_id: str | None = None, **body):
    matches = [{"itemId": i["id"], "medicineId": medicine_id or (i["medicine"] or {}).get("id")} for i in rx["items"]]
    return client.post(f"/prescriptions/{rx['id']}/check", headers=headers,
                       json={"checks": ALL_TICKED, "matches": matches, "status": "verified", **body})


@pytest.fixture
def stocked(client, ben):
    """Amoxicillin in two lots: one expiring sooner (first out), one later."""
    m = medicine(client, ben)
    receive(client, ben, [lot(m["id"], "LATE", 400, 100), lot(m["id"], "SOON", 60, 10)])
    return m


def test_a_prescription_goes_in_the_inbox_until_someone_checks_it(client, cy, ben, stocked):
    rx = take_in(client, cy)
    assert rx["status"] == "received" and rx["number"].startswith(f"RX-{TODAY.year}-")
    assert [p["id"] for p in client.get("/prescriptions?view=inbox", headers=cy).json()] == [rx["id"]]
    # The assistant took it in, but may not pass it.
    assert verify(client, cy, rx, stocked["id"]).status_code == 403

    # Checked part of the way: pending, not verified.
    ticks = {k: k in ("patient", "prescriber") for k in CHECK_KEYS}
    r = client.post(f"/prescriptions/{rx['id']}/check", headers=ben, json={"checks": ticks, "status": "pending"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending" and r.json()["checkedBy"]["name"] == "Ben Cruz"
    assert client.get("/prescriptions/counts", headers=ben).json() == {"inbox": 0, "pending": 1, "verified": 0, "attention": 0}


def test_verifying_needs_every_check_and_every_medicine_matched(client, ben, stocked):
    rx = take_in(client, ben)  # as written, not matched yet
    some = {**ALL_TICKED, "availability": False}
    r = client.post(f"/prescriptions/{rx['id']}/check", headers=ben, json={"checks": some, "status": "verified"})
    assert r.status_code == 422 and "Medicine availability" in r.text
    r = client.post(f"/prescriptions/{rx['id']}/check", headers=ben, json={"checks": ALL_TICKED, "status": "verified"})
    assert r.status_code == 409 and "isn't matched" in r.json()["detail"]
    r = verify(client, ben, rx, stocked["id"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "verified"


def test_a_problem_needs_a_note_and_a_rejection_closes_it(client, ben, stocked):
    rx = take_in(client, ben, stocked["id"])
    r = client.post(f"/prescriptions/{rx['id']}/check", headers=ben, json={"checks": {}, "status": "needs_clarification"})
    assert r.status_code == 422
    r = client.post(f"/prescriptions/{rx['id']}/check", headers=ben,
                    json={"checks": {}, "status": "needs_clarification", "notes": "Strength unclear; call the doctor."})
    assert r.json()["status"] == "needs_clarification"
    # Once answered, it can be checked again.
    assert verify(client, ben, rx).status_code == 200

    other = take_in(client, ben, stocked["id"])
    client.post(f"/prescriptions/{other['id']}/check", headers=ben, json={"checks": {}, "status": "rejected", "notes": "Forged."})
    assert verify(client, ben, other).status_code == 409


def test_old_future_or_dangerous_without_a_licence_cant_be_verified(client, ben, stocked):
    old = take_in(client, ben, stocked["id"], prescribedOn=(TODAY - timedelta(days=400)).isoformat())
    assert verify(client, ben, old).status_code == 409
    ahead = take_in(client, ben, stocked["id"], prescribedOn=(TODAY + timedelta(days=3)).isoformat())
    assert verify(client, ben, ahead).status_code == 409

    tramadol = medicine(client, ben, code="TRA50", rx_class="dangerous", genericName="Tramadol")
    rx = take_in(client, ben, tramadol["id"], prescriberLicense=None)
    r = verify(client, ben, rx)
    assert r.status_code == 409 and "licence" in r.json()["detail"]


def test_only_a_verified_prescription_is_dispensed(client, ben, cy, stocked):
    rx = take_in(client, ben, stocked["id"])
    batch = client.get(f"/medicines/{stocked['id']}", headers=ben).json()["batches"][0]
    line = {"itemId": rx["items"][0]["id"], "batchId": batch["id"], "quantity": 5}
    r = client.post("/dispensing", headers=ben, json={"prescriptionId": rx["id"], "lines": [line]})
    assert r.status_code == 409 and "isn't verified" in r.json()["detail"]
    assert client.get(f"/dispensing/prepare/{rx['id']}", headers=ben).status_code == 409

    verify(client, ben, rx)
    # The assistant can see the queue, but not hand things over.
    assert [p["id"] for p in client.get("/dispensing/queue", headers=cy).json()] == [rx["id"]]
    assert client.post("/dispensing", headers=cy, json={"prescriptionId": rx["id"], "lines": [line]}).status_code == 403


def test_dispensing_picks_batches_takes_stock_and_records_the_sale(client, ben, stocked):
    rx = verify(client, ben, take_in(client, ben, stocked["id"], qty=21)).json()
    prepared = client.get(f"/dispensing/prepare/{rx['id']}", headers=ben).json()
    batches = prepared["items"][0]["batches"]
    # First expiry, first out.
    assert [b["lotNo"] for b in batches] == ["SOON", "LATE"]
    item = rx["items"][0]["id"]

    # Part now: the whole of the soon lot and a few of the late one.
    r = client.post("/dispensing", headers=ben, json={"prescriptionId": rx["id"], "paymentMethod": "cash", "lines": [
        {"itemId": item, "batchId": batches[0]["id"], "quantity": 10},
        {"itemId": item, "batchId": batches[1]["id"], "quantity": 5},
    ]})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["number"].startswith("DS-") and first["units"] == 15
    assert [p["id"] for p in client.get("/dispensing/queue?view=partial", headers=ben).json()] == [rx["id"]]
    assert client.get("/dispensing/queue", headers=ben).json() == []

    sale = client.get(f"/sales/{first['saleId']}", headers=ben).json()
    assert sale["source"] == "dispensing" and sale["totalCentavos"] == 15 * 1250
    assert sale["dispensing"]["number"] == first["number"]
    stock = client.get(f"/medicines/{stocked['id']}", headers=ben).json()
    assert stock["onHand"] == 110 - 15
    moves = client.get(f"/stock/movements?medicineId={stocked['id']}&kind=dispense", headers=ben).json()["items"]
    assert sorted(m["quantity"] for m in moves) == [-10, -5] and {m["reference"] for m in moves} == {first["number"]}

    # More than is still owed is refused; the rest completes it.
    too_many = {"itemId": item, "batchId": batches[1]["id"], "quantity": 7}
    assert client.post("/dispensing", headers=ben, json={"prescriptionId": rx["id"], "lines": [too_many]}).status_code == 409
    rest = {"itemId": item, "batchId": batches[1]["id"], "quantity": 6}
    assert client.post("/dispensing", headers=ben, json={"prescriptionId": rx["id"], "lines": [rest]}).status_code == 201
    assert [p["id"] for p in client.get("/dispensing/queue?view=dispensed", headers=ben).json()] == [rx["id"]]
    detail = client.get(f"/prescriptions/{rx['id']}", headers=ben).json()
    assert detail["dispensed"] == "full" and len(detail["dispensings"]) == 2
    # Dispensed on, so its verification stands.
    assert verify(client, ben, rx).status_code == 409


def test_expired_quarantined_and_recalled_batches_cant_be_given_out(client, app, ben, stocked):
    rx = verify(client, ben, take_in(client, ben, stocked["id"], qty=5)).json()
    batches = {b["lotNo"]: b for b in client.get(f"/medicines/{stocked['id']}", headers=ben).json()["batches"]}
    item = rx["items"][0]["id"]

    def give(lot_no):
        return client.post("/dispensing", headers=ben, json={"prescriptionId": rx["id"],
                           "lines": [{"itemId": item, "batchId": batches[lot_no]["id"], "quantity": 1}]})

    r = client.post(f"/batches/{batches['SOON']['id']}/status", headers=ben, json={"status": "quarantined"})
    assert r.status_code == 422  # a reason, please
    client.post(f"/batches/{batches['SOON']['id']}/status", headers=ben, json={"status": "quarantined", "reason": "Seal broken."})
    assert "quarantine" in give("SOON").json()["detail"]
    held = client.get("/batches?view=held", headers=ben).json()["items"]
    assert [b["lotNo"] for b in held] == ["SOON"]

    client.post(f"/batches/{batches['LATE']['id']}/status", headers=ben, json={"status": "recalled", "reason": "Maker's recall."})
    assert "recalled" in give("LATE").json()["detail"]
    r = client.post(f"/batches/{batches['LATE']['id']}/status", headers=ben, json={"status": "available"})
    assert r.status_code == 409  # a recall is final

    with app.state.sessions() as db:
        b = db.get(Batch, batches["SOON"]["id"])
        b.status, b.expires_on = "available", TODAY - timedelta(days=1)
        db.commit()
    assert "expired" in give("SOON").json()["detail"]
    assert [b["lotNo"] for b in client.get("/batches?view=expired", headers=ben).json()["items"]] == ["SOON"]


def test_the_counter_sells_only_over_the_counter_medicines(client, cy, ben, stocked):
    r = client.post("/sales", headers=cy, json={"lines": [{"medicineId": stocked["id"], "quantity": 2}]})
    assert r.status_code == 409 and "verified prescription" in r.json()["detail"]

    pcm = medicine(client, ben, code="PCM500", rx_class="otc", price=450, genericName="Paracetamol")
    receive(client, ben, [lot(pcm["id"], "P-LATE", 500, 50), lot(pcm["id"], "P-SOON", 30, 3)])
    r = client.post("/sales", headers=cy, json={"lines": [{"medicineId": pcm["id"], "quantity": 5}], "discountCentavos": 50})
    assert r.status_code == 201, r.text
    sale = r.json()
    # The soon lot goes first, then the rest from the next.
    assert sorted((line["lotNo"], line["quantity"]) for line in sale["lines"]) == [("P-LATE", 2), ("P-SOON", 3)]
    assert sale["totalCentavos"] == 5 * 450 - 50
    assert client.post("/sales", headers=cy, json={"lines": [{"medicineId": pcm["id"], "quantity": 999}]}).status_code == 409
    assert client.get("/sales?view=today", headers=cy).json()["count"] == 1


def test_returns_put_stock_back_only_when_restocked_and_refunds_are_capped(client, ana, ben):
    pcm = medicine(client, ben, code="PCM500", rx_class="otc", price=450, genericName="Paracetamol")
    receive(client, ben, [lot(pcm["id"], "P1", 500, 20)])
    sale = client.post("/sales", headers=ben, json={"lines": [{"medicineId": pcm["id"], "quantity": 4}]}).json()
    line = sale["lines"][0]["id"]
    too_much = {"lines": [{"saleLineId": line, "quantity": 1}], "reason": "Wrong item", "refundCentavos": 9999, "refundMethod": "cash"}
    assert client.post(f"/sales/{sale['id']}/returns", headers=ben, json=too_much).status_code == 422
    r = client.post(f"/sales/{sale['id']}/returns", headers=ben, json={**too_much, "restock": True, "refundCentavos": 450})
    assert r.status_code == 201, r.text
    assert r.json()["refundedCentavos"] == 450 and r.json()["returns"][0]["number"].startswith("RT-")
    assert client.get(f"/medicines/{pcm['id']}", headers=ben).json()["onHand"] == 20 - 4 + 1
    # Not restocked: counted as returned, but nothing goes back on the shelf.
    client.post(f"/sales/{sale['id']}/returns", headers=ben, json={"lines": [{"saleLineId": line, "quantity": 3}], "reason": "Damaged"})
    assert client.get(f"/medicines/{pcm['id']}", headers=ben).json()["onHand"] == 17
    assert client.post(f"/sales/{sale['id']}/returns", headers=ben, json={"lines": [{"saleLineId": line, "quantity": 1}], "reason": "x"}).status_code == 409
    assert [r["refundCentavos"] for r in client.get("/sales/returns?view=refunds", headers=ben).json()] == [450]


def test_receiving_refuses_expired_lots_and_adjustments_explain_themselves(client, ben, cy):
    m = medicine(client, ben)
    bad = client.post("/stock/receivings", headers=cy, json={"receivedOn": TODAY.isoformat(), "lines": [lot(m["id"], "OLD", -1, 5)]})
    assert bad.status_code == 422
    received = receive(client, cy, [lot(m["id"], "A1", 200, 30)])
    assert received["number"].startswith("RC-") and received["units"] == 30
    batch = received["lines"][0]["batchId"]
    # The assistant receives, but doesn't adjust.
    assert client.post("/stock/adjustments", headers=cy, json={"batchId": batch, "quantity": -2, "reason": "Broken"}).status_code == 403
    r = client.post("/stock/adjustments", headers=ben, json={"batchId": batch, "quantity": -2, "reason": "Broken in the drawer"})
    assert r.status_code == 201 and r.json()["balance"] == 28
    assert client.post("/stock/adjustments", headers=ben, json={"batchId": batch, "quantity": -99, "reason": "x"}).status_code == 409
    low = client.get("/stock?view=low", headers=ben).json()["items"]
    assert low == []  # 28 on hand, reorder at 10


def test_medicines_with_history_are_discontinued_not_deleted(client, ben, stocked):
    assert client.delete(f"/medicines/{stocked['id']}", headers=ben).status_code == 409
    r = client.patch(f"/medicines/{stocked['id']}", headers=ben, json={"status": "discontinued"})
    assert r.json()["status"] == "discontinued"
    assert client.get("/medicines?state=discontinued", headers=ben).json()[0]["id"] == stocked["id"]


def test_reports_and_the_dashboard(client, ben, cy, stocked):
    take_in(client, cy, stocked["id"])
    dash = client.get("/dashboard", headers=cy).json()
    assert dash["prescriptions"]["inbox"] == 1 and dash["stock"]["expiring"] == 1  # the SOON lot
    listed = client.get("/reports", headers=ben).json()
    assert {"Prescriptions", "Dispensing", "Sales", "Inventory"} <= {r["group"] for r in listed}
    for r in listed:  # every report answers in the report kit's shape
        body = client.get(f"/reports/{r['key']}", headers=ben)
        assert body.status_code == 200, (r["key"], body.text)
        assert body.json()["columns"], r["key"]
    expiring = client.get("/reports/expiry", headers=ben).json()
    assert len(expiring["rows"]) == 1  # the SOON lot
    assert client.get("/reports", headers=cy).json() == []  # assistants don't read reports
    assert client.get("/reports/sales-summary", headers=cy).status_code == 403


def test_administration_is_the_administrators(client, ana, ben):
    assert client.get("/admin/users", headers=ben).status_code == 403
    users = client.get("/admin/users", headers=ana).json()
    assert {u["role"]["name"] for u in users["users"]} == {"Administrator", "Pharmacist", "Pharmacy Assistant"}
    admin_role = next(r["id"] for r in users["roles"] if r["name"] == "Administrator")
    me = next(u for u in users["users"] if u["email"] == "ana@example.com")
    pharmacist = next(r["id"] for r in users["roles"] if r["name"] == "Pharmacist")
    # Nobody left to administer: refused.
    assert client.patch(f"/admin/users/{me['id']}", headers=ana, json={"roleId": pharmacist}).status_code == 409
    assert client.patch(f"/admin/users/{me['id']}", headers=ana, json={"licenseNo": "PRC-1"}).json()["licenseNo"] == "PRC-1"
    assert admin_role
    log = client.get("/admin/audit?action=user.", headers=ana).json()["items"]
    assert log[0]["action"] == "user.updated" and log[0]["fields"] == ["licenseNo"]
