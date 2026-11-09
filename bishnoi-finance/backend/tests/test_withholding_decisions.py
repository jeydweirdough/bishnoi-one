"""Batch A (2026-11-05, Plans/Plan - Batch A withholding and supplier origin): Sir Mel's rules from recordings 11
and 12. Tax is withheld from local suppliers only; a foreign supplier (the user's rule: "Ltd" or "Limited" in the
name) has none. Every local line says what's withheld, or why nothing is, before it's confirmed and submitted; BIR
readiness lists the posted ones that don't. Made-up data."""

from datetime import date
from zoneinfo import ZoneInfo

import pytest

from app.bir_readiness import readiness
from app.models import Bill, Supplier
from app.payables import origin_by_name, withholding_decision

from .test_bill_flow import act
from .test_payables import account, supplier
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)
from .test_vouchers import team  # noqa: F401 (fixture)


def line(client, who, **extra) -> dict:
    return {"accountId": account(client, who, "6500"), "amountCentavos": 1_120_000, "vat": "vat", "withholding": None} | extra


def new_bill(client, who, supplier_id, lines, number="SI-0100", reviewed=True):
    return client.post("/finance/bills", json={"taxReviewed": reviewed, "supplierId": supplier_id, "billNumber": number,
                                                "billDate": "2026-10-01", "lines": lines}, headers=who)


def test_the_name_decides_local_or_foreign_and_a_person_can_change_it(client, team):
    assert [origin_by_name(n) for n in ("Hetero Labs Limited", "Beijing Beilu Pharmaceutical Co., Ltd.", "Biozenta Lifescience Pvt Ltd.",
                                        "Mercury Drug Corporation", "Ltdx Trading", "Limitless Supply Inc.")] == \
        ["foreign", "foreign", "foreign", "local", "local", "local"]
    aubrey = team["aubrey"]
    assert supplier(client, aubrey, name="Hetero Labs Limited", tin=None, withholding=None)["origin"] == "foreign"
    assert supplier(client, aubrey, name="Corner Packaging", tin=None, withholding=None)["origin"] == "local"
    # The branch of a foreign company here is local: a person says so.
    assert supplier(client, aubrey, name="Accord Healthcare Limited - Phil. Branch", tin=None, withholding=None, origin="local")["origin"] == "local"
    # A foreign supplier has no usual withholding.
    r = client.post("/finance/suppliers", json={"name": "Swiss Parenterals Ltd.", "withholding": "WC158"}, headers=aubrey)
    assert r.status_code == 422 and "foreign supplier" in r.text


def test_a_local_line_needs_a_code_or_a_reason_before_its_confirmed(client, team):
    aubrey = team["aubrey"]
    s = supplier(client, aubrey, withholding=None)
    refused = new_bill(client, aubrey, s["id"], [line(client, aubrey)])
    assert refused.status_code == 422 and "say why none is withheld" in refused.text
    assert refused.json()["detail"][0]["loc"][-1] == "noWithholdingReason"
    # "Other" needs a note.
    assert new_bill(client, aubrey, s["id"], [line(client, aubrey, noWithholdingReason="other")]).status_code == 422
    b = new_bill(client, aubrey, s["id"], [line(client, aubrey, noWithholdingReason="other", noWithholdingNote="Reimbursed at cost")])
    assert b.status_code == 201, b.text
    ln = b.json()["lines"][0]
    assert (ln["noWithholding"], ln["noWithholdingNote"], ln["noWithholdingLabel"]) == ("other", "Reimbursed at cost", "Other (see note)")
    # A code needs no reason; one given anyway isn't kept.
    coded = new_bill(client, aubrey, s["id"], [line(client, aubrey, withholding="WC158", noWithholdingReason="not_covered")], number="SI-0101").json()
    assert coded["lines"][0]["withholding"] == "WC158" and "noWithholding" not in coded["lines"][0]
    # A draft that isn't confirmed yet may leave it for later, but can't be submitted.
    draft = new_bill(client, aubrey, s["id"], [line(client, aubrey)], number="SI-0102", reviewed=False).json()
    assert draft["taxReviewed"] is False and draft["canSubmit"] is False
    act(client, aubrey, draft, "submit", expect=409)


def test_a_foreign_supplier_is_never_withheld_from(client, team):
    aubrey, malou = team["aubrey"], team["malou"]
    s = supplier(client, aubrey, name="Hetero Labs Limited", tin=None, withholding=None)
    for reviewed in (True, False):  # refused even in a draft
        r = new_bill(client, aubrey, s["id"], [line(client, aubrey, withholding="WC158")], reviewed=reviewed)
        assert r.status_code == 422 and "foreign supplier" in r.text
    b = new_bill(client, aubrey, s["id"], [line(client, aubrey, vat="none", purchaseType="importation")]).json()
    assert b["lines"][0]["noWithholding"] == "foreign" and b["lines"][0]["noWithholdingLabel"] == "Foreign supplier"
    act(client, aubrey, b, "submit")
    assert act(client, malou, b, "approve")["state"] == "ready"  # nothing withheld, so no tax check


def test_a_draft_confirmed_before_the_rule_is_checked_again_when_submitted(app, client, team):
    aubrey = team["aubrey"]
    s = supplier(client, aubrey, withholding=None)
    b = new_bill(client, aubrey, s["id"], [line(client, aubrey, noWithholdingReason="not_covered")]).json()
    with app.state.sessions() as db:  # as a draft saved before 2026-11-05 would be: confirmed, but with no reason
        row = db.get(Bill, b["id"])
        row.lines = [{k: v for k, v in ln.items() if k != "noWithholding"} for ln in row.lines]
        db.commit()
    refused = client.post(f"/finance/bills/{b['id']}/submit", headers=aubrey)
    assert refused.status_code == 409 and "Line 1" in refused.text
    # And a supplier found to be foreign after a line was withheld from.
    coded = new_bill(client, aubrey, s["id"], [line(client, aubrey, withholding="WC158")], number="SI-0103").json()
    with app.state.sessions() as db:
        db.get(Supplier, s["id"]).origin = "foreign"
        db.commit()
    refused = client.post(f"/finance/bills/{coded['id']}/submit", headers=aubrey)
    assert refused.status_code == 409 and "foreign supplier" in refused.text


def test_readiness_lists_posted_local_lines_with_no_decision(app, client, ana, team):
    aubrey, malou = team["aubrey"], team["malou"]
    local = supplier(client, aubrey, withholding=None)
    foreign = supplier(client, aubrey, name="Venus Remedies Limited", tin=None, withholding=None)
    decided = new_bill(client, aubrey, local["id"], [line(client, aubrey, noWithholdingReason="not_covered")]).json()
    old = new_bill(client, aubrey, local["id"], [line(client, aubrey, noWithholdingReason="not_covered")], number="SI-0104").json()
    imported = new_bill(client, aubrey, foreign["id"], [line(client, aubrey, vat="none")], number="INV-9").json()
    for b in (decided, old, imported):
        act(client, aubrey, b, "submit")
        act(client, malou, b, "approve")
    with app.state.sessions() as db:  # a bill posted before the rule: no reason on its line
        row = db.get(Bill, old["id"])
        row.lines = [{k: v for k, v in ln.items() if k != "noWithholding"} for ln in row.lines]
        db.commit()
        review = readiness(db, date(2026, 10, 1), date(2026, 10, 31), ZoneInfo("Asia/Manila"))["withholdingReview"]
    assert review["status"] == "needs_review" and review["missingCount"] == 1
    assert review["missing"][0]["href"] == f"/bills/{old['id']}" and review["missing"][0]["line"] == 1
    assert review["foreignLines"] == 1 and review["originNotSet"] == []


@pytest.mark.parametrize("origin, code, reason, note, complete, expected", [
    ("local", "WC158", None, None, True, ("WC158", None, None)),
    ("local", None, "not_covered", None, True, (None, "not_covered", None)),
    ("local", None, None, None, False, (None, None, None)),
    (None, None, "other", " Rebate ", True, (None, "other", "Rebate")),
    ("foreign", None, None, None, True, (None, "foreign", None)),
])
def test_the_decision_rule(origin, code, reason, note, complete, expected):
    assert withholding_decision(origin, code, reason, note, complete=complete) == expected


@pytest.mark.parametrize("origin, code, reason, note", [
    ("local", None, None, None), ("local", None, "foreign", None), ("local", None, "made_up", None), ("local", None, "other", ""), ("foreign", "WC158", None, None),
])
def test_the_decision_rule_refuses(origin, code, reason, note):
    with pytest.raises(ValueError):
        withholding_decision(origin, code, reason, note, complete=True)
