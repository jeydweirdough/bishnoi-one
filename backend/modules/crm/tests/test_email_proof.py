"""Emails logged before email from the CRM was dropped (2026-11-17) keep the
screenshot they were logged with, shown to whoever can see the email."""

from datetime import UTC, datetime

from modules.crm.models import Activity, StoredFile, User

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def logged_email(client, app, ana) -> tuple[str, str]:
    r = client.post("/companies", headers=ana, json={"name": "St. Luke's Medical Center", "email": "pharmacy@stlukes.test"})
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    with app.state.sessions() as db:
        me = db.query(User).filter(User.email == "ana@example.com").one()
        db.add(StoredFile(ref="a" * 32, content_type="image/png", data=PNG))
        now = datetime.now(UTC)
        a = Activity(kind="email", subject="Dosing guide", body="Sent from their own email app", at=now, done_at=now, direction="out",
                     company_id=cid, owner_id=me.id, team_id=me.team_id, created_by_id=me.id, proof_ref="a" * 32, proof_name="sent.png")
        db.add(a)
        db.commit()
        return cid, a.id


def test_an_older_emails_screenshot_is_still_shown(client, app, ana):
    cid, aid = logged_email(client, app, ana)
    shot = client.get(f"/activities/{aid}/proof", headers=ana)
    assert shot.status_code == 200 and shot.content == PNG and shot.headers["content-type"] == "image/png"
    page = client.get(f"/companies/{cid}", headers=ana).json()
    assert any(a["id"] == aid and a["hasProof"] for a in page["activities"])


def test_someone_who_cant_see_the_email_cant_see_its_screenshot(client, app, ana, ben):
    _, aid = logged_email(client, app, ana)
    assert client.get(f"/activities/{aid}/proof", headers=ben).status_code in (403, 404)


def test_writing_and_sending_email_from_the_crm_is_gone(client, ana):
    for path in ("/email/send", "/email/prepare", "/email/log"):
        assert client.post(path, headers=ana, json={}).status_code in (404, 405)
    for path in ("/mailbox", "/emails", "/email-templates", "/inbox", "/leads/finder"):
        assert client.get(path, headers=ana).status_code == 404
