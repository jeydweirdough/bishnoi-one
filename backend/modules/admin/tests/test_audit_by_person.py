"""Activity per person (2026-11-18, step 4F): ?person= reads only that person's own entries, behind the log's permission."""

from sqlalchemy import select

from modules.admin.models import AuditEntry, User
from modules.admin.tests.test_rbac import app, client, sign_in  # noqa: F401 (fixtures)


def _log(app, entries):
    """Adds lines straight to the log: (email, action), oldest first."""
    with app.state.sessions() as db:
        ids = {u.email: u.id for u in db.scalars(select(User))}
        for email, action in entries:
            db.add(AuditEntry(actor=email, actor_id=ids[email], action=action, target="x"))
        db.commit()


def test_one_persons_own_entries_newest_first(app, client):
    admin, other = sign_in(client), sign_in(client, "asst@example.com")
    _log(app, [("admin@example.com", "thing.one"), ("asst@example.com", "thing.two"), ("admin@example.com", "thing.three"), ("asst@example.com", "thing.four"), ("admin@example.com", "thing.five")])
    page = client.get("/admin/audit", params={"person": "ADMIN@EXAMPLE.COM", "limit": 2}, headers=admin).json()
    assert [e["action"] for e in page["items"]] == ["thing.five", "thing.three"] and page["more"] is True
    rest = client.get("/admin/audit", params={"person": "admin@example.com", "before": page["items"][-1]["id"]}, headers=admin).json()
    assert [e["action"] for e in rest["items"] if e["action"].startswith("thing.")] == ["thing.one"]
    assert {e["actor"] for e in rest["items"]} == {"admin@example.com"}
    theirs = client.get("/admin/audit", params={"person": "asst@example.com"}, headers=admin).json()["items"]
    assert [e["action"] for e in theirs if e["action"].startswith("thing.")] == ["thing.four", "thing.two"]
    assert {e["actor"] for e in theirs} == {"asst@example.com"}
    # Someone who isn't here has nothing; the whole log is unchanged.
    assert client.get("/admin/audit", params={"person": "nobody@example.com"}, headers=admin).json() == {"items": [], "more": False}
    assert len([e for e in client.get("/admin/audit", headers=admin).json()["items"] if e["action"].startswith("thing.")]) == 5


def test_reading_a_persons_activity_needs_the_log_permission(app, client):
    admin, other = sign_in(client), sign_in(client, "asst@example.com")
    assert client.get("/admin/audit", params={"person": "admin@example.com"}, headers=other).status_code == 403
