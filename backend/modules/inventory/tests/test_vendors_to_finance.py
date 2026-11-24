"""Every vendor added or changed here is sent to Finance, whose supplier follows it (2026-11-24: one vendor list)."""
from modules.inventory.tests.test_sales import outbox


def test_adding_changing_and_sending_all_vendors_tells_finance(app, ana, world):
    made = ana.post("/inventory/suppliers", {"code": "GC045604", "name": "Gloria Diaz Branch", "tin": "123456789000"})
    sent = outbox(app, "vendor.saved")
    assert sent[-1]["id"] == made["id"] and sent[-1]["name"] == "Gloria Diaz Branch" and sent[-1]["isActive"] is True
    ana.patch(f"/inventory/suppliers/{made['id']}", {"name": "Gloria Diaz Branch Inc."})
    assert outbox(app, "vendor.saved")[-1]["name"] == "Gloria Diaz Branch Inc."
    before = len(outbox(app, "vendor.saved"))
    every = ana.post("/inventory/suppliers/send-to-finance", {})
    assert every["sent"] >= 2 and len(outbox(app, "vendor.saved")) == before + every["sent"]
