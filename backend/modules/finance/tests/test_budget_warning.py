"""Over-budget warning (Sir Mel, recording 12): a bill or petty cash voucher not yet posted says when the
month's spending on an account would go over its budget, counting what the books already hold. A warning,
never a block. Made-up data."""

from .test_bill_flow import act
from .test_concurrent_saves import app  # noqa: F401 (the SQLite / PostgreSQL fixture)
from .test_payables import account, supplier
from .test_petty_cash import fund, voucher
from .test_tax_api import ana, ben, client  # noqa: F401 (fixtures)
from .test_vouchers import team  # noqa: F401 (fixture)

MONTH = 1_500_000  # ₱15,000 a month on 6500


def budget(client, who, months=None) -> None:
    r = client.put("/finance/budgets", headers=who, json={"yearEnd": "2026-12-31", "accountId": account(client, who, "6500"),
                                                           "months": months or [MONTH] * 12})
    assert r.status_code == 200, r.text


def draft(client, who, s, number, amount) -> dict:
    line = {"accountId": account(client, who, "6500"), "amountCentavos": amount, "vat": "vat", "withholding": None, "noWithholdingReason": "not_covered"}
    r = client.post("/finance/bills", json={"taxReviewed": True, "supplierId": s["id"], "billNumber": number, "billDate": "2026-10-01", "lines": [line]}, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_draft_bill_warns_when_it_would_go_over_and_counts_what_is_posted(client, ana, team):
    aubrey, malou = team["aubrey"], team["malou"]
    budget(client, ana)
    s = supplier(client, aubrey, withholding=None)
    first = draft(client, aubrey, s, "SI-B01", 1_120_000)  # ₱10,000 before VAT: within ₱15,000
    assert first["overBudget"] == []
    big = draft(client, aubrey, s, "SI-B02", 2_240_000)  # ₱20,000 on its own: ₱5,000 over
    [w] = big["overBudget"]
    assert (w["code"], w["month"], w["budgetCentavos"], w["postedCentavos"], w["thisCentavos"], w["overCentavos"]) == \
           ("6500", "2026-10", MONTH, 0, 2_000_000, 500_000)
    # Posting the first: the books now hold ₱10,000, so another ₱10,000 is ₱5,000 over.
    act(client, aubrey, first, "submit")
    posted = act(client, malou, first, "approve")
    assert posted["overBudget"] == []  # posted: already in the books, no warning on itself
    again = client.get(f"/finance/bills/{draft(client, aubrey, s, 'SI-B03', 1_120_000)['id']}", headers=aubrey).json()
    assert [(x["postedCentavos"], x["overCentavos"]) for x in again["overBudget"]] == [(1_000_000, 500_000)]
    # A warning, not a block: it can still be submitted.
    assert again["canSubmit"] is True


def test_no_budget_or_another_month_gives_no_warning(client, ana, team):
    aubrey = team["aubrey"]
    s = supplier(client, aubrey, withholding=None)
    assert draft(client, aubrey, s, "SI-B10", 9_999_999)["overBudget"] == []  # no budget set
    budget(client, ana, months=[MONTH] * 9 + [0, MONTH, MONTH])  # October (10th month) has none
    assert draft(client, aubrey, s, "SI-B11", 112)["overBudget"][0]["budgetCentavos"] == 0


def test_a_petty_cash_voucher_warns_too(app, client, ana):
    budget(client, ana, months=[50_000] * 12)  # ₱500 a month
    v = voucher(client, ana, fund(app))  # ₱1,120 with VAT: ₱1,000 before VAT
    [w] = v["overBudget"]
    assert (w["month"], w["thisCentavos"], w["overCentavos"]) == ("2026-10", 100_000, 50_000)
