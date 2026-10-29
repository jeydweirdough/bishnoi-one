"""Payables home and current aging agree with authoritative bill/voucher workflows."""

from datetime import date, timedelta

import pytest

from app.models import Bill, JournalEntry, OPEN_VOUCHERS, PaymentVoucher, Supplier, VoucherLine
from .test_dashboard import person
from .test_payables import bill, supplier
from .test_tax_api import app, ana, ben, client  # noqa: F401
from .test_vouchers import prepare, ready_bill, step, team  # noqa: F401


def work(client, who):
    r = client.get("/finance/dashboard/payables", headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def queues(client, who):
    return {q["key"]: q for q in work(client, who)["queues"]}


def test_handoffs_and_drilldowns_follow_existing_permissions(client, ana, team):
    a, m, r, c = (team[k] for k in ("aubrey", "malou", "rommel", "cristal"))
    s = supplier(client, a)
    b = bill(client, a, s["id"])
    assert queues(client, a)["bills_drafts"]["count"] == 1
    client.post(f"/finance/bills/{b['id']}/submit", headers=a)
    assert "bills_approve" not in queues(client, a)
    assert queues(client, m)["bills_approve"]["count"] == 1
    sent = queues(client, a)["bills_sent_approve"]
    assert "Waiting 0 calendar" in sent["details"][0]["note"]
    href = sent["href"].replace("/finance/", "/finance/", 1)
    assert [x["id"] for x in client.get(href, headers=a).json()["items"]] == [b["id"]]
    client.post(f"/finance/bills/{b['id']}/return", json={"reason": "Attach the receipt"}, headers=m)
    assert "Attach the receipt" in queues(client, a)["bills_returned"]["details"][0]["note"]
    assert "bills_returned" not in queues(client, c)
    client.post(f"/finance/bills/{b['id']}/submit", headers=a)
    client.post(f"/finance/bills/{b['id']}/approve", headers=m)
    assert "bills_check" not in queues(client, m)
    assert queues(client, r)["bills_check"]["count"] == 1
    assert queues(client, a)["bills_sent_check"]["count"] == 1
    assert work(client, a)["aging"]["totals"]["owedCentavos"] == 0
    client.post(f"/finance/bills/{b['id']}/check", headers=r)
    assert queues(client, c)["bills_prepare"]["count"] == 1
    assert client.get("/finance/dashboard", headers=ana).json()["kept"] is True
    assert work(client, ana)["aging"]["totals"]["owedCentavos"] == b["payableCentavos"]


@pytest.mark.parametrize("status", OPEN_VOUCHERS)
def test_every_open_voucher_reserves_without_reducing_owed(app, client, team, status):
    s, b = ready_bill(client, team)
    v = prepare(client, team["aubrey"], s, [{"billId": b["id"], "amountCentavos": 500000}])
    with app.state.sessions() as db:
        db.get(PaymentVoucher, v["id"]).status = status
        db.commit()
    data = client.get("/finance/payables/aging", headers=team["aubrey"]).json()
    assert data["totals"] == {"owedCentavos": 1110000, "reservedCentavos": 500000, "availableCentavos": 610000}
    assert work(client, team["aubrey"])["aging"]["totals"] == data["totals"]
    assert queues(client, team["cristal"])["bills_prepare"]["availableCentavos"] == 610000


def test_release_and_void_restore_balances_and_reservations(client, team):
    s, b = ready_bill(client, team)
    v = prepare(client, team["aubrey"], s, [{"billId": b["id"], "amountCentavos": 500000}])
    step(client, team["aubrey"], v, "submit")
    assert queues(client, team["cristal"])["vouchers_release"]["count"] == 1
    step(client, team["cristal"], v, "release", {"paidOn": date.today().isoformat()})
    data = work(client, team["aubrey"])["aging"]
    assert data["totals"] == {"owedCentavos": 610000, "reservedCentavos": 0, "availableCentavos": 610000}
    step(client, team["malou"], v, "void", {"reason": "Test reversal"})
    assert work(client, team["aubrey"])["aging"]["totals"] == {"owedCentavos": 1110000, "reservedCentavos": 0, "availableCentavos": 1110000}


def test_one_voucher_can_hold_two_bills_and_cancelling_frees_both(client, team):
    a, c = team["aubrey"], team["cristal"]
    s, first = ready_bill(client, team)
    second = bill(client, a, s["id"], number="SECOND")
    for who, action in ((a, "submit"), (team["malou"], "approve"), (team["rommel"], "check")):
        assert client.post(f"/finance/bills/{second['id']}/{action}", headers=who).status_code == 200
    v = prepare(client, a, s, [{"billId": b["id"], "amountCentavos": b["payableCentavos"]} for b in (first, second)])
    assert "bills_prepare" not in queues(client, c)
    assert queues(client, a)["vouchers_drafts"]["count"] == 1
    assert work(client, a)["aging"]["billCount"] == 2
    assert work(client, a)["aging"]["totals"]["availableCentavos"] == 0
    step(client, a, v, "cancel", {"reason": "Test only"})
    assert queues(client, c)["bills_prepare"]["count"] == 2
    assert work(client, a)["aging"]["totals"]["reservedCentavos"] == 0


def test_aging_boundaries_inactive_supplier_csv_and_large_lists(app, client, ana):
    on = date.fromisoformat(work(client, ana)["on"])
    with app.state.sessions() as db:
        s = Supplier(name="Fictional supplies", created_by="Test", is_active=False)
        db.add(s)
        # As in real use (2026-10-29: aging is rebuilt from dated events): a recorded bill has its
        # posted entry, and what's paid on it was paid by a released voucher.
        entry = JournalEntry(number="JE-TEST-0001", entry_date=on - timedelta(days=100), memo="Synthetic bills", source="bill", posted_by="Test")
        db.add(entry)
        db.flush()
        paid = []
        for i, days in enumerate([0, 1, 30, 31, 60, 61, 90, 91]):
            b = Bill(supplier_id=s.id, bill_number=f"EDGE-{i}", bill_date=on-timedelta(days=100), due_date=on-timedelta(days=days),
                     status="recorded", payable_centavos=10000, paid_centavos=1000, created_by="Test", entry_id=entry.id)
            db.add(b)
            paid.append((b, 1000))
        # More than the old 300-row limit; also prove drafts and paid/void bills are omitted.
        for i in range(302):
            db.add(Bill(supplier_id=s.id, bill_number=f"BULK-{i}", bill_date=on, due_date=on, status="recorded", payable_centavos=100, created_by="Test", entry_id=entry.id))
        for status, amount in (("draft", 0), ("void", 0), ("recorded", 100)):
            b = Bill(supplier_id=s.id, bill_number=f"EXCLUDED-{status}", bill_date=on, due_date=on, status=status,
                     payable_centavos=100, paid_centavos=amount, created_by="Test")
            db.add(b)
            if status == "recorded":
                b.entry_id = entry.id
                paid.append((b, 100))
        db.flush()
        db.add(PaymentVoucher(number="PV-TEST-0001", status="released", supplier_id=s.id, total_centavos=sum(a for _, a in paid),
                              prepared_by="Test", paid_on=on - timedelta(days=50), entry_id=entry.id,
                              lines=[VoucherLine(bill_id=b.id, position=i, amount_centavos=a) for i, (b, a) in enumerate(paid)]))
        db.commit()
        sid = s.id
    report = client.get("/finance/payables/aging", headers=ana).json()
    assert report["billCount"] == 310
    assert [b["amountCentavos"] for b in report["buckets"]] == [39200, 18000, 18000, 18000, 9000]
    for bucket in report["buckets"]:
        found = client.get(f"/finance/bills?queue=outstanding&supplierId={sid}&bucket={bucket['key']}", headers=ana).json()
        assert sum(b["leftCentavos"] for b in found["items"]) == bucket["amountCentavos"]
    assert len(client.get("/finance/bills?queue=outstanding", headers=ana).json()["items"]) == 310
    csv = client.get("/finance/payables/aging?format=csv&bucket=d1_30", headers=ana)
    assert csv.status_code == 200 and "Fictional supplies" in csv.text and "180.00" in csv.text
    assert "Total" in csv.text
    assert client.get("/finance/payables/aging?bucket=nonsense", headers=ana).status_code == 422


def test_permissions_and_team_drafts_do_not_guess_creator_identity(client, ana):
    s = supplier(client, ana)
    bill(client, ana, s["id"])
    viewer = person(client, ana, "Bills viewer", ["dashboard.view", "bills.view"])
    assert work(client, viewer)["aging"] is not None
    assert "bills_drafts" not in queues(client, viewer)
    assert client.get("/finance/bills?queue=approve", headers=viewer).json()["items"] == []
    vouchers_only = person(client, ana, "Voucher reader", ["dashboard.view", "vouchers.view"])
    assert work(client, vouchers_only)["aging"] is None
    assert client.get("/finance/payables/aging", headers=vouchers_only).status_code == 403
    none = person(client, ana, "No payables", ["dashboard.view"])
    assert client.get("/finance/dashboard/payables", headers=none).status_code == 403
    maker = person(client, ana, "Other maker", ["dashboard.view", "bills.view", "bills.create"])
    assert queues(client, maker)["bills_drafts"]["label"] == "Draft bills"


def test_due_groups_do_not_overlap_and_self_approval_is_excluded(app, client, ana, team):
    from app.access import access_of
    from app.payables_work import filter_bills
    from app.models import User
    from sqlalchemy import select

    with app.state.sessions() as db:
        user = db.scalar(select(User).where(User.email == "ana@example.com"))
        assert access_of(user).can("bills.approve")
        for day in (1, 15, 16, 31):
            on = date(2026, 10, day)
            rows = [Bill(id=f"due-{i}", status="recorded", payable_centavos=100, paid_centavos=0, due_date=date(2026,10,i),
                         submitted_by_id=user.id, stage=None, created_by="Test") for i in range(1,32)]
            groups = [filter_bills(rows, user, on, {}, queue=q) for q in ("overdue", "by_15", "month_end")]
            ids = [b.id for g in groups for b in g]
            assert len(ids) == len(set(ids)) == 31
        own = Bill(id="own", status="draft", stage="to_approve", submitted_by_id=user.id, paid_centavos=0, payable_centavos=100)
        assert filter_bills([own], user, date(2026,10,26), {}, queue="approve") == []
