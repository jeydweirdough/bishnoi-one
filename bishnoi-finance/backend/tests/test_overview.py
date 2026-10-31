"""The Living Overview (2026-10-31, Plans/Plan - Living Overview per account): each permission set gets exactly
its cards and slices; only approved entries count; each picture's total is its list's total; whoever made a
record doesn't see it as theirs to check; no date is invented; nothing recorded yet is a page of zeros."""

import json
import re
from datetime import UTC, date, datetime, timedelta

import pytest

from app import overview as ov
from app.bir_reports import quarter
from app.models import ExpenseCategory, FundExpense, FundRequest, ZohoSourceDocument
from app.permissions import ALL_PERMISSIONS, PER_PERSON

from .test_dashboard import VIEW, person
from .test_invoices import issued, ready
from .test_ledger import approve as approved_by_ana
from .test_ledger import accounts
from .test_payables import account, bill, supplier
from .test_petty_cash import MAKER, attach_all, fund, line
from .test_concurrent_saves import app  # noqa: F401 (the SQLite / PostgreSQL fixture)
from .test_tax_api import ana, ben, client  # noqa: F401 (fixtures)
from .test_vouchers import prepare, step, team  # noqa: F401 (fixtures)

TODAY = date.today()
ON = TODAY.isoformat()
EVERYTHING = sorted(ALL_PERMISSIONS - PER_PERSON)
# The local test accounts' permissions (the design's table), so each hero is the approved one.
ERICA = "dashboard.view bills.view categories.view invoices.view journal.view sales_orders.view suppliers.view vouchers.view"
MEL = "accounts.manage accounts.view admin.audit bank.reconcile bank.view bills.check bills.view bir.prepare bir.view categories.view dashboard.view funds.view imports.confirm_tax imports.propose invoices.view journal.post journal.reverse journal.view petty_cash.check petty_cash.create petty_cash.view petty_cash.void sales_orders.view suppliers.view tax.manage tax.view vouchers.view"
CRISTAL = "accounts.manage accounts.view admin.audit bank.reconcile bank.view bills.approve bills.create bills.view bir.view categories.manage categories.view dashboard.view funds.cancel funds.check funds.release funds.settle funds.view imports.confirm imports.propose imports.run invoices.collect invoices.create invoices.issue invoices.setup invoices.view invoices.void journal.approve journal.post journal.reverse journal.view petty_cash.check petty_cash.create petty_cash.view petty_cash.void prices.approve prices.view sales_orders.view suppliers.add suppliers.deactivate suppliers.edit suppliers.view tax.manage tax.view vouchers.prepare vouchers.release vouchers.view vouchers.void"
AUBREY = "accounts.view bills.create bills.view categories.manage categories.view dashboard.view invoices.create invoices.setup invoices.view journal.post journal.view petty_cash.create petty_cash.view sales_orders.view suppliers.add suppliers.deactivate suppliers.edit suppliers.view tax.view vouchers.prepare vouchers.view"
MALOU = "accounts.manage accounts.view admin.audit bank.reconcile bank.view bills.approve bills.first bills.view bills.void bir.prepare bir.view categories.manage categories.view dashboard.view funds.cancel funds.check funds.view imports.confirm invoices.collect invoices.create invoices.issue invoices.setup invoices.view invoices.void journal.approve journal.first journal.post journal.reverse journal.view petty_cash.check petty_cash.create petty_cash.view petty_cash.void prices.approve prices.view sales_orders.approve sales_orders.cancel sales_orders.create sales_orders.submit sales_orders.view suppliers.add suppliers.deactivate suppliers.edit suppliers.view tax.manage tax.view vouchers.view vouchers.void"


def see(client, who, period="month") -> dict:
    r = client.get(f"/finance/overview?period={period}", headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def everyone(client, ana, name="Sees everything") -> dict:
    return person(client, ana, name, EVERYTHING)


def hand_entry(client, who, memo="Capital put in", amount=500_000) -> dict:
    """An entry typed by hand: it waits for someone else, into the bank (a money account)."""
    acc = accounts(client, who)
    r = client.post("/finance/ledger/entries", json={"date": ON, "memo": memo, "lines": [
        {"accountId": acc["1010"]["id"], "debitCentavos": amount}, {"accountId": acc["3000"]["id"], "creditCentavos": amount}]}, headers=who)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "waiting"
    return r.json()


def figures(view: dict) -> dict:
    """The cards' figures, without the list of what's waiting (a waiting entry is meant to show there)."""
    return {k: v for k, v in view["cards"].items() if k != "wait"}


@pytest.mark.parametrize(("permissions", "cards", "lead", "tabs"), [
    ([], set(), "none", {"overview"}),
    (["dashboard.view"], set(), "none", {"overview"}),
    (["invoices.view"], {"ar", "od", "coll", "due", "zoho"}, "recv", {"overview", "receivables"}),
    (["bills.view"], {"ap", "went", "soon"}, "sup", {"overview", "payables"}),
    (["petty_cash.view"], {"petty", "went"}, "petty", {"overview", "cash"}),
    (["funds.view"], {"mkt", "went"}, "none", {"overview"}),
    (["journal.view"], {"inout", "books"}, "none", {"overview"}),
    (["accounts.view"], set(), "none", {"overview"}),
    (["accounts.view", "journal.view"], {"cash", "inout", "books"}, "cash", {"overview", "cash"}),
    (["bir.view"], {"vat", "ewt", "ready", "dl"}, "vat", {"overview", "tax"}),
    (["integrations.manage"], {"link"}, "none", {"overview"}),
    (["bills.approve"], set(), "none", {"overview"}),  # the doing without the view opens nothing
    (["bills.view", "bills.approve"], {"ap", "went", "soon", "wait"}, "sup", {"overview", "payables"}),
])
def test_each_permission_set_gets_exactly_its_cards(client, ana, permissions, cards, lead, tabs):
    who = person(client, ana, "One set", permissions)
    view = see(client, who)
    assert set(view["cards"]) == cards
    assert set(view["views"]) == tabs
    assert view["views"]["overview"]["lead"] == lead
    for v in view["views"].values():
        assert len(v["cards"]) <= 5 and set(v["cards"]) <= set(view["cards"])
    assert {p["key"] for p in view["pickable"]} <= set(view["cards"])


def test_a_mixed_picture_shows_only_the_slices_its_viewer_may_see(client, ana):
    made = iter(range(99))
    only = lambda perms: see(client, person(client, ana, f"Went {next(made)}", perms))["cards"]["went"]  # noqa: E731
    assert [s["key"] for s in only(["bills.view"])["slices"]] == ["bills"]
    assert only(["bills.view"])["hidden"] == ["petty cash", "marketing"]
    assert [s["key"] for s in only(["petty_cash.view"])["slices"]] == ["petty"]
    assert [s["key"] for s in only(["funds.view"])["slices"]] == ["marketing"]
    assert [s["key"] for s in only(["bills.view", "petty_cash.view", "funds.view"])["slices"]] == ["bills", "petty", "marketing"]


def test_nothing_else_is_sent_with_a_card(client, ana):
    """The answer of someone who may see only invoices says nothing of bills, cash or tax."""
    text = json.dumps(see(client, person(client, ana, "Invoices only", ["invoices.view"])))
    for word in ("cash-disbursements", "/finance/bills", "/finance/bir", "petty", "/finance/funds"):
        assert word not in text


@pytest.mark.parametrize(("permissions", "lead", "overview_cards"), [
    (ERICA, "recv", ["zoho", "od", "coll", "due"]),
    (MEL, "vat", ["wait", "ready", "ewt", "books", "dl"]),
    (CRISTAL, "release", ["wait", "cash", "petty", "mkt", "went"]),
    (AUBREY, "mine", ["wait", "ap", "petty", "went", "soon"]),
    (MALOU, "cash", ["wait", "ar", "ap", "vat", "went"]),
])
def test_the_hero_comes_from_what_someone_does_not_their_name(client, ana, permissions, lead, overview_cards):
    # A misleading role name on purpose.
    view = see(client, person(client, ana, "Finance Head BIR and Compliance", permissions.split()))
    assert view["views"]["overview"]["lead"] == lead
    assert view["views"]["overview"]["cards"] == overview_cards


def test_buttons_need_the_doing_permission(client, ana):
    reader = see(client, person(client, ana, "Reads petty cash", ["petty_cash.view"]))
    assert [a["label"] for a in reader["leads"]["petty"]["actions"]] == ["Open petty cash"]
    maker = see(client, person(client, ana, "Makes petty cash", MAKER))
    assert any(a["href"] == "/finance/petty-cash/new" for a in maker["leads"]["mine"]["actions"])
    recv = see(client, person(client, ana, "Reads invoices", ["invoices.view"]))["leads"]["recv"]
    assert recv["viewOnly"] and all("new" not in a["href"] for a in recv["actions"])
    for a in (recv["actions"][0], reader["leads"]["petty"]["actions"][0]):
        assert a["primary"]


def test_a_waiting_or_rejected_entry_changes_no_figure(client, ana, ben):
    malou = everyone(client, ana)
    before = {p: figures(see(client, malou, p)) for p in ("month", "quarter", "year")}
    entry = hand_entry(client, ben)
    for p, was in before.items():
        assert figures(see(client, malou, p)) == was
    # It waits for Malou, as a hand-off, not as a figure.
    assert [r["title"] for r in see(client, malou)["cards"]["wait"]["forYou"]] == [f"{entry['number']} · Capital put in"]
    rejected = client.post(f"/finance/ledger/entries/{entry['id']}/reject", json={"reason": "Wrong account"}, headers=ana)
    assert rejected.status_code == 200, rejected.text
    for p, was in before.items():
        assert figures(see(client, malou, p)) == was
    # And an approved one does count: the check above can fail.
    approved_by_ana(client, hand_entry(client, ben, "Capital, approved"))
    after = see(client, malou)["cards"]
    assert after["cash"]["balanceCentavos"] == 500_000 and after["inout"]["inCentavos"] == 500_000
    assert next(s for s in after["books"]["sources"] if s["key"] == "manual")["count"] == 1


def posted_bill(client, team, number, amount=1_120_000, on=ON, due=None) -> tuple[dict, dict]:
    s = supplier(client, team["aubrey"], name=f"Supplier {number}", tin=None)
    b = bill(client, team["aubrey"], s["id"], amount=amount, number=number, billDate=on, **({"dueDate": due} if due else {}))
    for who, act in ((team["aubrey"], "submit"), (team["malou"], "approve"), (team["rommel"], "check")):
        r = client.post(f"/finance/bills/{b['id']}/{act}", headers=who)
        assert r.status_code == 200, r.text
    return s, r.json()


def test_each_picture_totals_what_its_list_totals(app, client, ana, team):
    ready(client, ana)
    who = everyone(client, ana)
    # An invoice part-paid with tax withheld, and one in full view of the aging.
    inv = issued(client, ana)
    issued(client, ana, customerName="Rose Pharmacy")
    r = client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": ON, "amountCentavos": 100_000, "method": "cash"}, headers=ana)
    assert r.status_code in (200, 201), r.text
    # A bill part-paid through a released voucher, another still owed.
    s, b = posted_bill(client, team, "SI-1")
    posted_bill(client, team, "SI-2", amount=560_000)
    v = prepare(client, team["aubrey"], s, [{"billId": b["id"], "amountCentavos": 500_000}])
    step(client, team["aubrey"], v, "submit")
    step(client, team["cristal"], v, "release", {"paidOn": ON, "bankReference": "BDO-1"})
    # A posted petty cash voucher, and one still a draft that must not count.
    f = fund(app)
    maker = person(client, ana, "Petty maker", MAKER)
    pv = attach_all(client, maker, voucher_today(client, maker, f))
    client.post(f"/finance/petty-cash/{pv['id']}/submit", headers=maker)
    posted = client.post(f"/finance/petty-cash/{pv['id']}/check", headers=ana)
    assert posted.status_code == 200, posted.text
    voucher_today(client, maker, f, number="2MG PCV DRAFT")

    for period in ("month", "quarter", "year"):
        view = see(client, who, period)
        c = view["cards"]
        start, end = date.fromisoformat(view["period"]["start"]), date.fromisoformat(view["period"]["end"])
        span = f"start={start}&end={min(end, TODAY)}"
        # Owed by customers and to suppliers: everything here is dated in the period.
        aged = client.get("/finance/receivables", headers=who).json()
        assert c["ar"]["wholeCentavos"] == c["ar"]["periodCentavos"] == aged["totalCentavos"] == 2 * 224_000 - 100_000
        assert {b_["key"]: b_["amountCentavos"] for b_ in c["ar"]["buckets"]} == {b_["key"]: b_["amountCentavos"] for b_ in aged["buckets"]}
        owed = client.get("/finance/payables/aging", headers=who).json()
        assert c["ap"]["wholeCentavos"] == c["ap"]["periodCentavos"] == owed["totals"]["owedCentavos"]
        assert {b_["key"]: b_["amountCentavos"] for b_ in c["ap"]["buckets"]} == {b_["key"]: b_["amountCentavos"] for b_ in owed["buckets"]}
        # The bars open the same bills.
        listed = client.get("/finance/bills?queue=outstanding&bucket=current", headers=who).json()["items"]
        assert sum(x["leftCentavos"] for x in listed) == next(b_ for b_ in c["ap"]["buckets"] if b_["key"] == "current")["amountCentavos"]
        # Tax: as the books of account, the return and the lists read it.
        sales = client.get(f"/finance/bir/books/sales-journal?{span}", headers=who).json()["totals"]
        buys = client.get(f"/finance/bir/books/purchase-journal?{span}", headers=who).json()["totals"]
        assert c["vat"]["outputCentavos"] == sales["taxCentavos"] and c["vat"]["inputCentavos"] == buys["inputTaxCentavos"]
        assert sum(p["amountCentavos"] for p in c["vat"]["output"]) == sales["taxCentavos"]
        assert sum(p["amountCentavos"] for p in c["vat"]["input"]) == buys["inputTaxCentavos"]
        assert c["ewt"]["totalCentavos"] == buys["ewtCentavos"] > 0
        receipts = client.get(f"/finance/bir/books/cash-receipts?{span}", headers=who).json()["totals"]
        assert c["coll"]["totalCentavos"] == receipts["cashCentavos"] == 100_000
        # Paid out is the Cash Disbursements Journal (nothing here waits, so it holds no unapproved entries).
        paid = client.get(f"/finance/bir/books/cash-disbursements?{span}", headers=who).json()["totals"]
        assert c["inout"]["outCentavos"] == paid["amountCentavos"] > 0
        ready_list = client.get(f"/finance/bir/readiness?{span}", headers=who).json()
        assert c["ready"]["counts"] == ready_list["counts"]
        # Books by source: every approved entry in the period, as the journal lists them.
        entries = client.get(f"/finance/ledger/entries?from={start}&to={end}&status=approved&limit=500", headers=who).json()["items"]
        assert c["books"]["entries"] == len(entries)
        assert c["books"]["totalCentavos"] == sum(e["totalCentavos"] for e in entries)
        # Spending: posted and recorded only; the draft voucher and draft bills aren't in it.
        went = {x["key"]: x for x in c["went"]["slices"]}
        assert went["bills"]["amountCentavos"] == 1_680_000 and went["bills"]["count"] == 2
        assert went["petty"]["amountCentavos"] == posted.json()["totalCentavos"] and went["petty"]["count"] == 1
    quarter_view = see(client, who, "quarter")["cards"]
    today_quarter = (TODAY.month - 1) // 3 + 1
    vat = client.get(f"/finance/bir/returns/vat?year={TODAY.year}&quarter={today_quarter}", headers=who).json()
    lines = {x["key"]: x.get("amountCentavos") for x in vat["lines"]}
    assert (quarter_view["vat"]["outputCentavos"], quarter_view["vat"]["inputCentavos"]) == (lines["output"], lines["input"])
    assert abs(quarter_view["vat"]["payableCentavos"]) == lines["payable"]
    qap = client.get(f"/finance/bir/lists/qap?year={TODAY.year}&quarter={today_quarter}", headers=who).json()
    assert quarter_view["ewt"]["totalCentavos"] == qap["totals"]["taxCentavos"]
    # The fund's gauge is its balance in the books, as the petty cash page shows it.
    funds = client.get("/finance/petty-cash", headers=who).json()["funds"]
    assert see(client, who)["cards"]["petty"]["balanceCentavos"] == sum(x["balanceCentavos"] for x in funds)


def voucher_today(client, who, fund_id, number="2MG PCV 1") -> dict:
    r = client.post("/finance/petty-cash", json={"number": number, "fundAccountId": fund_id, "voucherDate": ON, "lines": [line(client, who, spentOn=ON)]}, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def test_an_aging_older_than_the_period_stays_in_the_whole_figure(client, ana, team):
    """A bill from an earlier year: not in this month's picture, still in what's owed, as the aging list shows it."""
    who = everyone(client, ana)
    old = date(TODAY.year - 2, 1, 15).isoformat()
    posted_bill(client, team, "SI-OLD", on=old, due=date(TODAY.year - 2, 2, 15).isoformat())
    ap = see(client, who)["cards"]["ap"]
    assert ap["periodCentavos"] == 0 and ap["wholeCentavos"] == ap["over60Centavos"] > 0
    assert ap["wholeBills"] == 1 and ap["periodBills"] == 0


def test_only_recorded_bills_count(client, ana, team):
    who = everyone(client, ana)
    s = supplier(client, team["aubrey"], tin=None)
    b = bill(client, team["aubrey"], s["id"], billDate=ON)
    client.post(f"/finance/bills/{b['id']}/submit", headers=team["aubrey"])
    c = see(client, who)["cards"]
    assert c["ap"]["wholeCentavos"] == 0 and c["went"]["slices"][0]["amountCentavos"] == 0
    assert c["vat"]["inputCentavos"] == 0 and c["ewt"]["totalCentavos"] == 0


def test_a_maker_never_sees_their_own_record_as_theirs_to_check(app, client, ana):
    both = person(client, ana, "Makes and approves", ["accounts.view", "suppliers.view", "suppliers.add", "bills.view", "bills.create", "bills.approve", "bills.check", "petty_cash.view", "petty_cash.create", "petty_cash.check"])
    other = person(client, ana, "Approves only", ["bills.view", "bills.approve", "petty_cash.view", "petty_cash.check"])
    s = supplier(client, both, tin=None)
    b = bill(client, both, s["id"], billDate=ON)
    assert client.post(f"/finance/bills/{b['id']}/submit", headers=both).status_code == 200
    f = fund(app)
    v = attach_all(client, both, voucher_today(client, both, f))
    assert client.post(f"/finance/petty-cash/{v['id']}/submit", headers=both).status_code == 200

    mine = see(client, both)["cards"]["wait"]
    assert mine["forYou"] == [] and mine["forYouTotal"] == 0
    assert sorted(r["title"] for r in mine["others"]) == ["1 bill waiting for approval", "1 petty cash voucher waiting to be checked"]
    theirs = see(client, other)["cards"]["wait"]
    assert theirs["forYouTotal"] == 2 and theirs["others"] == []
    assert {r["href"] for r in theirs["forYou"]} == {f"/finance/bills/{b['id']}", f"/finance/petty-cash/{v['id']}"}
    assert theirs["byArea"] == {"payables": 1, "receivables": 0, "cash": 1}
    assert see(client, other)["counts"] == {"payables": 1, "cash": 1, "overview": 2}
    # Whoever approved a bill doesn't also check its tax, and sees it on the other side.
    assert client.post(f"/finance/bills/{b['id']}/approve", headers=other).status_code == 200
    after = see(client, other)["cards"]["wait"]
    assert [r["title"] for r in after["others"]] == ["1 bill you approved waiting for the tax check"]


def test_a_journal_entry_is_not_its_posters_to_approve(client, ana):
    both = person(client, ana, "Posts and approves", ["accounts.view", "journal.view", "journal.post", "journal.approve"])
    hand_entry(client, both)
    wait = see(client, both)["cards"]["wait"]
    assert wait["forYouTotal"] == 0 and wait["others"][0]["title"] == "1 journal entry waiting for approval"
    other = person(client, ana, "Approves entries", ["accounts.view", "journal.view", "journal.approve"])
    assert see(client, other)["cards"]["wait"]["forYouTotal"] == 1


def fund_request(db, number, status, released_by=None, team_name="Hospital team", spent=None) -> FundRequest:
    now = datetime.now(UTC)
    r = FundRequest(source_app="crm", source_id=number, number=number, requester_name="Rico Santos", requester_email="rico@example.com", team_name=team_name,
                    purpose="Dinner", requested_centavos=500_000, approved_centavos=500_000, approved_by_name="Sir", approved_at=now, status=status,
                    released_centavos=500_000 if status != "to_release" else None, released_at=now if status != "to_release" else None, released_by_id=released_by)
    db.add(r)
    db.flush()
    if spent:
        category = db.query(ExpenseCategory).filter(ExpenseCategory.parent_id.is_(None), ExpenseCategory.account_id.is_not(None)).first()
        r.checked_at = now
        for amount, accepted in spent:
            db.add(FundExpense(request_id=r.id, spent_on=TODAY, description="Dinner", category_id=category.id, amount_centavos=amount, accepted=accepted))
    return r


def test_marketing_counts_only_accepted_receipts_on_reviewed_liquidations_by_team(app, client, ana):
    who = person(client, ana, "Marketing reader", ["funds.view"])
    with app.state.sessions() as db:
        fund_request(db, "FR-1", "closed", spent=[(120_000, True), (50_000, False)])
        fund_request(db, "FR-2", "closed", team_name="Drugstore team", spent=[(80_000, True)])
        fund_request(db, "FR-3", "to_check", team_name="Not reviewed")
        db.commit()
    c = see(client, who)["cards"]
    assert [(t["label"], t["amountCentavos"], t["count"]) for t in c["mkt"]["teams"]] == [("Hospital team", 120_000, 1), ("Drugstore team", 80_000, 1)]
    assert c["mkt"]["totalCentavos"] == c["went"]["slices"][0]["amountCentavos"] == 200_000


def test_whoever_released_money_does_not_review_it(app, client, ana):
    both = person(client, ana, "Releases and reviews", ["funds.view", "funds.release", "funds.check"])
    me = client.get("/finance/frame", headers=both).json()["me"]["user"]["id"]
    with app.state.sessions() as db:
        fund_request(db, "FR-MINE", "to_check", released_by=me)
        fund_request(db, "FR-OTHER", "to_check")
        fund_request(db, "FR-NEW", "to_release")
        db.commit()
    view = see(client, both)
    assert sorted(r["title"].split(" · ")[0] for r in view["cards"]["wait"]["forYou"]) == ["FR-NEW", "FR-OTHER"]
    lead = view["leads"]["release"]
    assert lead["count"] == 1 and lead["totalCentavos"] == 500_000
    assert lead["actions"][0]["href"] == "/finance/funds?stage=to_release"


def test_no_date_is_invented(client, ana):
    who = person(client, ana, "BIR reader", ["bir.view"])
    deadlines = see(client, who)["cards"]["dl"]
    assert deadlines == {"listed": False}
    # Coming up holds only real due dates and the country's holidays.
    reader = person(client, ana, "Bills reader", ["bills.view"])
    soon = see(client, reader)["cards"]["soon"]
    assert all(r["meta"] == "Day off" for r in soon["rows"])
    assert soon["total"] == len(soon["rows"]) or len(soon["rows"]) == ov.LISTED


def test_nothing_recorded_is_a_page_of_zeros(client, ana):
    who = everyone(client, ana)
    for period in ("month", "quarter", "year"):
        view = see(client, who, period)
        c = view["cards"]
        assert view["counts"]["overview"] == 0
        assert c["cash"]["balanceCentavos"] == 0 and all(p["amountCentavos"] == 0 for p in c["cash"]["points"])
        assert c["inout"]["inCentavos"] == c["inout"]["outCentavos"] == 0
        assert c["ar"]["wholeCentavos"] == c["ap"]["wholeCentavos"] == 0 and all(b["amountCentavos"] == 0 for b in c["ar"]["buckets"] + c["ap"]["buckets"])
        assert c["vat"]["outputCentavos"] == c["vat"]["inputCentavos"] == c["ewt"]["totalCentavos"] == 0
        assert c["mkt"]["teams"] == [] and c["petty"]["balanceCentavos"] == 0
        assert c["went"]["totalCentavos"] == 0 and c["wait"]["forYou"] == []
        assert c["od"]["rows"] == [] and c["books"]["entries"] == 0
        assert len(c["books"]["sources"]) >= 5  # the picture keeps its shape, at zero
    assert client.get("/finance/overview?period=decade", headers=who).status_code == 422


def test_books_by_source_fit_a_card_and_lose_nothing(app, client, ana):
    """Six kinds of entry: the smallest join "Other sources", typed by hand always shows, the total stays whole."""
    from app.ledger import Leg, post
    from app.models import Account

    who = person(client, ana, "Reads the journal", ["journal.view"])
    with app.state.sessions() as db:
        bank, capital = (db.query(Account).filter(Account.code == c).one() for c in ("1010", "3000"))
        for i, source in enumerate(("bill", "voucher", "petty_cash", "invoice", "fund", "manual", "pack")):
            post(db, TODAY, f"Entry {source}", [Leg(bank, debit=(i + 1) * 100), Leg(capital, credit=(i + 1) * 100)], "Tester", reference=None, source=source)
        db.commit()
    books = see(client, who)["cards"]["books"]
    keys = [r["key"] for r in books["sources"]]
    assert len(keys) == ov.BOOK_ROWS and "manual" in keys and keys[-1] == "other"
    assert sum(r["amountCentavos"] for r in books["sources"]) == books["totalCentavos"] == 2800
    assert sum(r["count"] for r in books["sources"]) == books["entries"] == 7


def test_the_period_sets_the_bars(client, ana):
    who = person(client, ana, "BIR reader", ["bir.view"])
    bars = {p: len(see(client, who, p)["cards"]["vat"]["output"]) for p in ("month", "quarter", "year")}
    assert bars["quarter"] == 3 and bars["year"] == 12 and 4 <= bars["month"] <= 6
    view = see(client, who, "quarter")
    p = quarter(TODAY.year, (TODAY.month - 1) // 3 + 1)
    assert (view["period"]["start"], view["period"]["end"]) == (p.start.isoformat(), p.end.isoformat())


def zoho_invoice(db, source_id, company, date_, due, balance, currency="PHP", status="sent") -> None:
    db.add(ZohoSourceDocument(organization_id="org-1", kind="invoice", source_id=source_id, data={
        "id": source_id, "number": f"INV-{source_id}", "date": date_, "dueDate": due, "status": status, "customerName": f"Customer {source_id}",
        "company": company, "currency": currency, "balanceCentavos": balance, "totalCentavos": balance}))


def test_zoho_copies_are_counted_apart_and_only_when_connected(app, client, ana, monkeypatch):
    who = person(client, ana, "Reads Zoho", ["invoices.view"])
    # Not connected here: said plainly, no figures.
    assert see(client, who)["cards"]["zoho"] == {"available": False}
    assert see(client, who)["cards"]["due"]["available"] is False
    monkeypatch.setattr("app.routers.zoho_source.organization", lambda settings: "org-1")
    last_week, tomorrow = (TODAY - timedelta(days=7)).isoformat(), (TODAY + timedelta(days=1)).isoformat()
    with app.state.sessions() as db:
        zoho_invoice(db, "1", "2mg", ON, tomorrow, 100_000)
        zoho_invoice(db, "2", "gpi", ON, ON, 50_000)
        zoho_invoice(db, "3", "unknown", ON, "", 25_000)
        zoho_invoice(db, "4", "2mg", ON, last_week, 10_000)
        zoho_invoice(db, "5", "2mg", ON, tomorrow, 0, status="paid")
        zoho_invoice(db, "6", "2mg", ON, tomorrow, 999_000, status="void")
        zoho_invoice(db, "7", "2mg", ON, tomorrow, 777_000, currency="USD")
        zoho_invoice(db, "8", "2mg", ON, tomorrow, None)
        db.commit()
    c = see(client, who)["cards"]
    z = c["zoho"]
    assert z["totalCentavos"] == 185_000 and z["count"] == 4 and z["notCounted"] == 2
    assert {x["key"]: x["amountCentavos"] for x in z["companies"]} == {"2mg": 110_000, "gpi": 50_000, "unknown": 25_000}
    assert {x["key"]: x["amountCentavos"] for x in z["buckets"]} == {"current": 150_000, "d1_30": 10_000, "d31_60": 0, "d61_90": 0, "over_90": 0, "no_due": 25_000}
    # Due this week, soonest first, each opening the saved copy. None of it is in the books.
    assert [r["title"] for r in c["due"]["rows"]] == ["INV-2 · Customer 2", "INV-1 · Customer 1"]
    assert c["due"]["rows"][0]["chip"]["text"] == "Due today" and c["due"]["rows"][1]["href"] == "/finance/invoices/zoho/1"
    assert c["ar"]["wholeCentavos"] == 0


def every_href(value, found=None) -> list[str]:
    found = [] if found is None else found
    if isinstance(value, dict):
        for k, v in value.items():
            if k in ("href", "queue", "seeAll") and v:
                found.append(v)
            else:
                every_href(v, found)
    elif isinstance(value, list):
        for v in value:
            every_href(v, found)
    return found


# The Finance pages a card may link to (app/(app)/finance), each with a filter it really reads.
PAGES = re.compile(r"^/finance/(bills(/aging|/new|/[0-9a-f-]{36})?|vouchers(/[0-9a-f-]{36})?|funds(/[0-9a-f-]{36})?|ledger(/accounts|/trial-balance)?|invoices(/receivables|/zoho(/[^/?]+)?)?"
                   r"|petty-cash(/new|/[0-9a-f-]{36})?|sales-orders(/local|/[0-9a-f-]{36})?|bir(/vat|/withholding|/lists|/readiness)?|bank|calendar|integrations/zoho|prices)(\?.*)?$")


def test_every_link_goes_to_a_real_page(client, ana, team):
    who = everyone(client, ana)
    posted_bill(client, team, "SI-LINK")
    for period in ("month", "quarter", "year"):
        links = every_href(see(client, who, period))
        assert links
        assert [x for x in links if not PAGES.match(x)] == []


def test_the_bank_is_a_money_account_the_cash_picture_reads(app, client, ana):
    from app.money_accounts import money_account_ids

    with app.state.sessions() as db:
        assert account(client, ana, "1010") in money_account_ids(db)
