"""When the CRM can't send an email (no mailbox, or the provider refused): it's
copied into the person's own email app, and logged with a screenshot of it sent."""

import json

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def customer(client, ana) -> str:
    r = client.post("/companies", headers=ana, json={"name": "St. Luke's Medical Center", "email": "pharmacy@stlukes.test"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_prepared_then_logged_with_its_screenshot(client, ana):
    cid = customer(client, ana)
    email = {"companyId": cid, "to": ["pharmacy@stlukes.test"], "subject": "Dosing guide", "body": "Here's the guide we discussed."}
    ready = client.post("/email/prepare", headers=ana, json=email).json()
    assert ready == {"to": ["pharmacy@stlukes.test"], "subject": "Dosing guide", "body": "Here's the guide we discussed."}

    # No screenshot, or not a picture: nothing is logged.
    assert client.post("/email/log", headers=ana, data={"email": json.dumps(email)}).status_code == 422
    r = client.post("/email/log", headers=ana, data={"email": json.dumps(email)}, files={"proof": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 422 and "screenshot" in r.text

    r = client.post("/email/log", headers=ana, data={"email": json.dumps(email)}, files={"proof": ("sent.png", PNG, "image/png")})
    assert r.status_code == 201, r.text
    logged = r.json()
    assert logged["kind"] == "email" and logged["hasProof"] and "own email app" in logged["body"]
    shot = client.get(f"/activities/{logged['id']}/proof", headers=ana)
    assert shot.status_code == 200 and shot.content == PNG and shot.headers["content-type"] == "image/png"

    # It's on the customer's page, as an email.
    page = client.get(f"/companies/{cid}", headers=ana).json()
    assert any(a["id"] == logged["id"] and a["hasProof"] for a in page["activities"])


def test_someone_who_cant_see_the_email_cant_see_its_screenshot(client, ana, ben):
    cid = customer(client, ana)
    email = {"companyId": cid, "to": ["pharmacy@stlukes.test"], "subject": "Hello", "body": "Hi."}
    logged = client.post("/email/log", headers=ana, data={"email": json.dumps(email)}, files={"proof": ("sent.png", PNG, "image/png")}).json()
    assert client.get(f"/activities/{logged['id']}/proof", headers=ben).status_code in (403, 404)
