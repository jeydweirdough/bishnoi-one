"""Payment vouchers (2026-10-23, Plans/Plan - Payment vouchers; checks moved to the bill the same
day, Plans/Plan - Bill approval flow): only bills ready to pay go on one; prepared → released,
which posts it; returned with a reason back to whoever prepared it; part of a bill paid and shown;
nothing paid twice; whoever prepared it may release it; Malou voids. Made-up data."""

import pytest

from app.routers.vouchers import in_words

from .test_dashboard import VIEW, person
from .test_ledger import balances
from .test_payables import account, bill, supplier
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

PAYABLES = ["suppliers.view", "bills.view", "vouchers.view"]


@pytest.fixture
def team(client, ana):
    """As set on your PC (2026-10-23): Aubrey makes bills and may prepare vouchers; Malou approves
    bills (told first) and voids; Mel/Rommel checks the tax withheld; Cristal approves bills as
    backup, and prepares and releases the payment."""
    return {
        "aubrey": person(client, ana, "Accounts Payable", VIEW + PAYABLES + ["suppliers.add", "bills.create", "vouchers.prepare"]),
        "rommel": person(client, ana, "BIR and Compliance", VIEW + PAYABLES + ["bills.check"]),
        "cristal": person(client, ana, "Finance Deputy", VIEW + PAYABLES + ["bills.create", "bills.approve", "vouchers.prepare", "vouchers.release"]),
        "malou": person(client, ana, "Finance Head", VIEW + PAYABLES + ["bills.approve", "bills.first", "bills.void", "vouchers.void"]),
    }


def ready_bill(client, team, number="SI-0001", amount=1_120_000) -> tuple[dict, dict]:
    """Aubrey makes and submits it, Malou approves it, Rommel checks the tax withheld: ready to pay."""
    aubrey = team["aubrey"]
    s = supplier(client, aubrey)
    b = bill(client, aubrey, s["id"], amount=amount, number=number)
    for who, action in ((aubrey, "submit"), (team["malou"], "approve"), (team["rommel"], "check")):
        r = client.post(f"/finance/bills/{b['id']}/{action}", headers=who)
        assert r.status_code == 200, r.text
    assert r.json()["state"] == "ready"
    return s, r.json()


def prepare(client, who, s, lines, **extra) -> dict:
    body = {"supplierId": s["id"], "method": "bank", "paidFromId": account(client, who, "1010"), "lines": lines} | extra
    r = client.post("/finance/vouchers", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def step(client, who, v, action, body=None, expect=200) -> dict:
    r = client.post(f"/finance/vouchers/{v['id']}/{action}", json=body or {}, headers=who)
    assert r.status_code == expect, r.text
    return r.json()


def kinds(client, who) -> list[str]:
    return [n["kind"] for n in client.get("/finance/notifications", headers=who).json()["items"]]


def test_a_voucher_pays_part_of_a_bill_and_cristal_releases_it(client, ana, team):
    aubrey, cristal, malou = team["aubrey"], team["cristal"], team["malou"]
    s, b = ready_bill(client, team)  # ₱11,100 to pay
    v = prepare(client, aubrey, s, [{"billId": b["id"], "amountCentavos": 500_000}], oojeemaRef="PV-0099", zohoRef="ZP-12")
    assert v["number"].startswith("PV-") and v["status"] == "draft" and v["totalCentavos"] == 500_000
    line = v["lines"][0]
    # Part of the bill, plainly: its total, paid before, paying now, left after (decision 4).
    assert (line["payableCentavos"], line["paidBeforeCentavos"], line["amountCentavos"], line["leftAfterCentavos"], line["partial"]) == (1_110_000, 0, 500_000, 610_000, True)
    # The bill's own approvals travel with it onto the voucher.
    assert (line["approvedBy"], line["checkedBy"]) == ("Finance Head", "BIR and Compliance")
    assert step(client, aubrey, v, "submit")["status"] == "to_release"  # no other OK in the Hub
    assert "voucher.to_release" in kinds(client, cristal) and "voucher.to_release" not in kinds(client, aubrey)
    done = step(client, cristal, v, "release", {"paidOn": "2026-10-02", "bankReference": "BDO-778899"})
    assert done["status"] == "released" and done["releasedBy"] == "Finance Deputy"
    assert done["amountInWords"] == "Five thousand pesos and 00/100"
    # Posted: payables down, the bank down; the bill partly paid, shown on the bill and the supplier.
    assert balances(client, ana)["2000"] == 610_000 and balances(client, ana)["1010"] == -500_000
    paid = client.get(f"/finance/bills/{b['id']}", headers=aubrey).json()
    assert (paid["paidCentavos"], paid["leftCentavos"], paid["paymentLabel"], paid["state"]) == (500_000, 610_000, "Partly paid", "partly_paid")
    assert paid["vouchers"][0]["number"] == v["number"]
    owed = next(x for x in client.get("/finance/suppliers", headers=aubrey).json()["items"] if x["id"] == s["id"])["owedCentavos"]
    assert owed == 610_000
    assert "voucher.released" in kinds(client, aubrey)
    signed = client.get(f"/finance/signatures/payment_voucher/{v['id']}", headers=malou).json()["steps"]
    assert [x["step"] for x in signed] == ["prepared", "released"]


def test_only_bills_ready_to_pay_go_on_a_voucher(client, team):
    aubrey = team["aubrey"]
    s = supplier(client, aubrey)
    b = bill(client, aubrey, s["id"])
    client.post(f"/finance/bills/{b['id']}/submit", headers=aubrey)  # waiting for Malou
    assert client.get("/finance/vouchers/choices", headers=aubrey).json()["suppliers"] == []
    waiting = client.post("/finance/vouchers", json={"supplierId": s["id"], "paidFromId": account(client, aubrey, "1010"),
                                                    "lines": [{"billId": b["id"], "amountCentavos": 100}]}, headers=aubrey)
    assert waiting.status_code == 422 and "ready to pay" in waiting.text


def test_nothing_is_paid_twice(client, team):
    aubrey = team["aubrey"]
    s, b = ready_bill(client, team)
    first = prepare(client, aubrey, s, [{"billId": b["id"], "amountCentavos": 600_000}])
    too_much = client.post("/finance/vouchers", json={"supplierId": s["id"], "paidFromId": account(client, aubrey, "1010"),
                                                      "lines": [{"billId": b["id"], "amountCentavos": 600_000}]}, headers=aubrey)
    assert too_much.status_code == 422 and "set aside in another voucher" in too_much.text
    choices = client.get(f"/finance/vouchers/choices?supplier={s['id']}", headers=aubrey).json()
    assert choices["bills"][0]["setAsideCentavos"] == 600_000 and choices["bills"][0]["availableCentavos"] == 510_000
    step(client, aubrey, first, "cancel", {"reason": "Wrong amount"})
    prepare(client, aubrey, s, [{"billId": b["id"], "amountCentavos": 1_110_000}])  # all of it, once the first is cancelled


def test_whoever_prepared_it_may_release_it_and_returning_is_for_someone_else(client, team):
    aubrey, cristal = team["aubrey"], team["cristal"]
    s, b = ready_bill(client, team)
    v = prepare(client, cristal, s, [{"billId": b["id"], "amountCentavos": 100_000}])
    step(client, cristal, v, "submit")
    step(client, cristal, v, "return", {"reason": "My own"}, expect=403)  # she prepared it: she cancels it instead
    step(client, aubrey, v, "release", {"paidOn": "2026-10-02"}, expect=403)  # preparing isn't releasing
    assert step(client, cristal, v, "release", {"paidOn": "2026-10-02"})["status"] == "released"


def test_returned_with_a_reason_goes_back_and_is_submitted_again(client, team):
    aubrey, rommel, cristal = team["aubrey"], team["rommel"], team["cristal"]
    s, b = ready_bill(client, team)
    v = prepare(client, aubrey, s, [{"billId": b["id"], "amountCentavos": 100_000}])
    step(client, aubrey, v, "submit")
    back = step(client, cristal, v, "return", {"reason": "Wrong bank account"})
    assert back["status"] == "returned"
    assert back["events"][-1] == back["events"][-1] | {"kind": "returned", "who": "Finance Deputy", "text": "Wrong bank account"}
    assert "voucher.returned" in kinds(client, aubrey)
    step(client, rommel, v, "return", {"reason": "again"}, expect=409)  # already back with Aubrey
    fixed = client.put(f"/finance/vouchers/{v['id']}", json={"supplierId": s["id"], "paidFromId": account(client, aubrey, "1000"),
                                                            "lines": [{"billId": b["id"], "amountCentavos": 100_000}]}, headers=aubrey)
    assert fixed.status_code == 200
    again = step(client, aubrey, v, "submit")
    assert again["status"] == "to_release" and again["events"][-1]["kind"] == "resubmitted"


def test_malou_voids_a_released_voucher_and_the_bill_is_owed_again(client, ana, team):
    aubrey, cristal, malou = team["aubrey"], team["cristal"], team["malou"]
    s, b = ready_bill(client, team)
    v = prepare(client, aubrey, s, [{"billId": b["id"], "amountCentavos": 1_110_000}], method="check")
    step(client, aubrey, v, "submit")
    step(client, cristal, v, "release", {"paidOn": "2026-10-02"}, expect=422)  # a check needs its number
    step(client, cristal, v, "release", {"paidOn": "2026-10-02", "checkNumber": "000123", "checkDate": "2026-10-02"})
    assert client.get(f"/finance/bills/{b['id']}", headers=aubrey).json()["paymentLabel"] == "Paid"
    # A bill a voucher has paid can't be voided until the voucher is.
    assert client.post(f"/finance/bills/{b['id']}/void", json={"reason": "test"}, headers=ana).status_code == 409
    step(client, cristal, v, "void", {"reason": "Bounced"}, expect=403)  # Malou only (decision 7)
    gone = step(client, malou, v, "void", {"reason": "Check bounced"})
    assert gone["status"] == "void"
    bill_now = client.get(f"/finance/bills/{b['id']}", headers=aubrey).json()
    assert (bill_now["paidCentavos"], bill_now["leftCentavos"], bill_now["state"]) == (0, 1_110_000, "ready")
    assert balances(client, ana)["2000"] == 1_110_000 and balances(client, ana)["1010"] == 0


def test_vouchers_pay_from_the_accounts_under_cash(client, ana, team):
    cash = client.post("/finance/ledger/accounts", json={"code": "0001-000", "name": "CASH", "type": "asset"}, headers=ana).json()
    bdo = client.post("/finance/ledger/accounts", json={"code": "1215-2MG", "name": "Cash in Bank - Test Bank", "type": "asset", "parentId": cash["id"]}, headers=ana).json()
    offered = {a["code"] for a in client.get("/finance/vouchers/choices", headers=team["aubrey"]).json()["accounts"]}
    # Under CASH, plus the money accounts already set under Default accounts; not every asset.
    assert "1215-2MG" in offered and "1010" in offered and "1200" not in offered and "1300" not in offered
    s, b = ready_bill(client, team)
    refused = client.post("/finance/vouchers", json={"supplierId": s["id"], "paidFromId": account(client, ana, "1200"),
                                                    "lines": [{"billId": b["id"], "amountCentavos": 100}]}, headers=team["aubrey"])
    assert refused.status_code == 422
    assert bdo["parentId"] == cash["id"]


def test_amounts_in_words():
    assert in_words(1_110_050) == "Eleven thousand one hundred pesos and 50/100"
    assert in_words(100) == "One peso and 00/100"
    assert in_words(123_456_789_00) == "One hundred twenty-three million four hundred fifty-six thousand seven hundred eighty-nine pesos and 00/100"


def test_the_voucher_ticks_have_their_own_labels(client, ana):
    catalogue = {a["key"]: [x["label"] for x in a["actions"]] for a in client.get("/admin/roles", headers=ana).json()["catalogue"]}
    assert catalogue["vouchers"] == ["View", "Prepare (make, edit, submit, cancel)", "Release (pay)", "Void a released voucher"]
    assert catalogue["funds"][2] == "Review liquidations"  # the shared label stays where it was
