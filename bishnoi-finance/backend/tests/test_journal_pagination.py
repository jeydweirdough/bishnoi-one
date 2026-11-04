"""Journal paging must reach older entries without changing filters or exports."""
from datetime import date
from sqlalchemy import select
from app.models import JournalEntry, User
from .test_tax_api import app, client, ana  # noqa: F401


def test_every_entry_is_reachable_and_totals_follow_filters(app, client, ana):
    with app.state.sessions() as db:
        who = db.scalar(select(User).where(User.email == "ana@example.com"))
        db.add_all(JournalEntry(number=f"PAGE-{i:04}", entry_date=date(2026, 1, 1),
                               memo="Pagination example", source="manual" if i % 2 else "invoice",
                               posted_by=who.full_name, posted_by_id=who.id, status="approved") for i in range(207))
        db.commit()
    ids = []
    for offset in range(0, 207, 25):
        r = client.get(f"/finance/ledger/entries?limit=25&offset={offset}&q=Pagination", headers=ana)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 207
        ids.extend(e["id"] for e in data["items"])
    assert len(ids) == len(set(ids)) == 207
    filtered = client.get("/finance/ledger/entries?source=manual&limit=10&offset=100", headers=ana).json()
    assert filtered["total"] == 103 and len(filtered["items"]) == 3
    assert client.get("/finance/ledger/entries?from=2026-02-01", headers=ana).json()["total"] == 0
    assert client.get("/finance/ledger/entries?offset=-1", headers=ana).status_code == 422
    assert client.get("/finance/ledger/entries?limit=501", headers=ana).status_code == 422
    assert client.get("/finance/ledger/entries?offset=500", headers=ana).json()["items"] == []
