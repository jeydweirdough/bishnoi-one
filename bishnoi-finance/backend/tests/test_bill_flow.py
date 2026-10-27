"""A supplier bill's approval, as Aubrey described it (2026-10-23, Plans/Plan - Bill approval
flow): Aubrey makes and submits it; Malou approves it (told first; Cristal is backup); only if
tax is withheld, Mel checks it; then it's posted and ready to pay, and Cristal is told.
Returned with a reason, it goes back to Aubrey and, corrected, to approval again. Whoever
submitted it does no later step; whoever approved it doesn't check it. Made-up data."""

from .test_ledger import balances
from .test_payables import account, bill, supplier
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)
from .test_vouchers import kinds, team  # noqa: F401 (fixture)


def act(client, who, b, action, body=None, expect=200) -> dict:
    r = client.post(f"/finance/bills/{b['id']}/{action}", json=body, headers=who) if body else client.post(f"/finance/bills/{b['id']}/{action}", headers=who)
    assert r.status_code == expect, r.text
    return r.json()


def test_a_bill_without_tax_withheld_clears_when_malou_approves(client, ana, team):
    aubrey, cristal, malou = team["aubrey"], team["cristal"], team["malou"]
    s = supplier(client, aubrey, withholding=None)
    plain = {"accountId": account(client, aubrey, "6500"), "amountCentavos": 1_120_000, "vat": "vat", "withholding": None}
    b = client.post("/finance/bills", json={"taxReviewed": True, "supplierId": s["id"], "billNumber": "SI-0100", "billDate": "2026-10-01", "lines": [plain]}, headers=aubrey).json()
    assert b["needsCheck"] is False and b["canSubmit"] is True
    act(client, aubrey, b, "submit")
    # Malou is told first; Cristal, the backup, isn't (decision 5).
    assert "bill.to_approve" in kinds(client, malou) and "bill.to_approve" not in kinds(client, cristal)
    done = act(client, malou, b, "approve")
    assert (done["status"], done["state"], done["approvedBy"], done["checkedBy"]) == ("recorded", "ready", "Finance Head", None)
    assert [e["kind"] for e in done["events"]] == ["tax_reviewed", "submitted", "approved", "cleared"]
    assert balances(client, ana)["2000"] == 1_120_000
    # Ready to pay: Cristal is told; the bell's item for Malou is done.
    assert "bill.ready" in kinds(client, cristal)
    signed = client.get(f"/finance/signatures/bill/{b['id']}", headers=malou).json()["steps"]
    assert [x["step"] for x in signed] == ["prepared", "approved"]


def test_a_bill_with_tax_withheld_is_checked_after_approval(client, ana, team):
    aubrey, rommel, malou = team["aubrey"], team["rommel"], team["malou"]
    s = supplier(client, aubrey)
    b = bill(client, aubrey, s["id"])  # 1% withheld (WC158)
    act(client, aubrey, b, "submit")
    approved = act(client, malou, b, "approve")
    assert (approved["status"], approved["state"], approved["stateLabel"]) == ("draft", "to_check", "To check")
    assert balances(client, ana) == {}  # not in the books until it clears (decision 1)
    assert "bill.to_check" in kinds(client, rommel)
    done = act(client, rommel, b, "check")
    assert (done["state"], done["approvedBy"], done["checkedBy"], done["recordedBy"]) == ("ready", "Finance Head", "BIR and Compliance", "BIR and Compliance")
    assert balances(client, ana)["2300"] == 10_000
    signed = client.get(f"/finance/signatures/bill/{b['id']}", headers=malou).json()["steps"]
    assert [x["step"] for x in signed] == ["prepared", "approved", "checked"]


def test_whoever_submitted_it_does_no_later_step_and_the_approver_doesnt_check(client, ana, team):
    cristal, malou = team["cristal"], team["malou"]
    s = supplier(client, team["aubrey"])
    b = bill(client, cristal, s["id"])
    act(client, cristal, b, "submit")
    act(client, cristal, b, "approve", expect=403)  # she submitted it
    act(client, malou, b, "approve")
    # Ana (Administrator) may approve and check; she checks nothing she approved.
    b2 = bill(client, cristal, s["id"], number="SI-0002")
    act(client, cristal, b2, "submit")
    act(client, ana, b2, "approve")
    act(client, ana, b2, "check", expect=403)


def test_returned_it_goes_back_to_aubrey_and_then_to_malou_again(client, ana, team):
    aubrey, rommel, malou = team["aubrey"], team["rommel"], team["malou"]
    s = supplier(client, aubrey)
    b = bill(client, aubrey, s["id"])
    act(client, aubrey, b, "submit")
    # Nothing is changed while it waits.
    line = {"accountId": account(client, aubrey, "6500"), "amountCentavos": 1_000_000, "vat": "vat", "withholding": "WC158"}
    body = {"taxReviewed": True, "supplierId": s["id"], "billNumber": "SI-0001", "billDate": "2026-10-01", "lines": [line]}
    assert client.put(f"/finance/bills/{b['id']}", json=body, headers=aubrey).status_code == 409
    act(client, aubrey, b, "return", {"reason": "Mine"}, expect=403)  # she submitted it
    act(client, malou, b, "approve")
    back = act(client, rommel, b, "return", {"reason": "Wrong ATC: it's a service"})
    assert (back["state"], back["approvedBy"]) == ("returned", None)
    assert back["events"][-1] == back["events"][-1] | {"kind": "returned", "who": "BIR and Compliance", "text": "Wrong ATC: it's a service"}
    assert "bill.returned" in kinds(client, aubrey)
    act(client, rommel, b, "return", {"reason": "again"}, expect=409)  # already back with Aubrey
    assert client.put(f"/finance/bills/{b['id']}", json=body, headers=aubrey).status_code == 200
    again = act(client, aubrey, b, "submit")
    # Back to Malou, from the start (decision 2).
    assert again["state"] == "to_approve" and again["events"][-1]["kind"] == "resubmitted"
    act(client, rommel, b, "check", expect=409)


def test_the_bills_list_has_a_tab_for_each_step(client, ana, team):
    aubrey, malou = team["aubrey"], team["malou"]
    s = supplier(client, aubrey)
    drafts = [bill(client, aubrey, s["id"], number=f"SI-{n}") for n in range(1, 5)]
    act(client, aubrey, drafts[1], "submit")
    act(client, aubrey, drafts[2], "submit")
    act(client, malou, drafts[2], "approve")
    act(client, aubrey, drafts[3], "submit")
    act(client, malou, drafts[3], "return", {"reason": "No PO"})
    listed = client.get("/finance/bills", headers=aubrey).json()
    assert {k: v for k, v in listed["counts"].items() if v} == {"draft": 1, "to_approve": 1, "to_check": 1, "returned": 1, "missing": 4}
    shown = client.get("/finance/bills?show=to_check", headers=aubrey).json()["items"]
    assert [x["id"] for x in shown] == [drafts[2]["id"]] and shown[0]["stateLabel"] == "To check"
    # Waiting bills aren't owed yet.
    assert next(x for x in client.get("/finance/suppliers", headers=aubrey).json()["items"] if x["id"] == s["id"])["owedCentavos"] == 0
