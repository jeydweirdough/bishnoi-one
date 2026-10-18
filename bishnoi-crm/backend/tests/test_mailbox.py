"""Each person's own mailbox (app/mailbox.py): connected by signing in with the
provider, or by SMTP; emails sent from it are kept on the customer. The
providers are stood in for here: nothing leaves the machine."""

from urllib.parse import parse_qs, urlparse

import pytest

from app import connections
from app import mailbox as mb
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)

GMAIL = {"client_id": "123.apps.googleusercontent.com", "client_secret": "google-secret-value"}


class Answer:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data


@pytest.fixture
def google(monkeypatch):
    """Google, stood in for: hands out tokens and takes what's sent."""
    sent = []

    def post(url, data=None, json=None, headers=None, timeout=None):
        if url.endswith("/token"):
            return Answer({"access_token": "at", "refresh_token": "rt-from-google"})
        sent.append(json)
        return Answer({"id": "m1"})

    monkeypatch.setattr(mb.httpx, "post", post)
    monkeypatch.setattr(mb.httpx, "get", lambda url, headers=None, timeout=None: Answer({"email": "ria@getmeds.ph"}))
    monkeypatch.setattr(mb, "redirect_uri", lambda settings: "https://crm.example.com/account/mailbox/callback")
    return sent


# The company's services as the platform gives them (Companies → the company → Connections).
ON: dict[str, dict] = {}


@pytest.fixture(autouse=True)
def platform_services(monkeypatch):
    ON.clear()
    monkeypatch.setattr(connections, "services", lambda settings, company=None: dict(ON))
    yield
    ON.clear()


def set_up_gmail(client, ana):
    """Gmail switched on for the company, on the platform."""
    ON["gmail"] = GMAIL


def test_connect_gmail_and_send_from_it(client, ana, crew, google):
    assert [p["ready"] for p in client.get("/mailbox", headers=crew["ria"]).json()["providers"]] == [False, False, False]
    set_up_gmail(client, ana)
    url = client.post("/mailbox/start", json={"provider": "gmail"}, headers=crew["ria"]).json()["url"]
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == [GMAIL["client_id"]] and "gmail.send" in q["scope"][0]
    # Someone else can't finish Ria's sign-in.
    assert client.post("/mailbox/finish", json={"state": q["state"][0], "code": "c"}, headers=crew["rex"]).status_code == 409
    box = client.post("/mailbox/finish", json={"state": q["state"][0], "code": "c"}, headers=crew["ria"]).json()
    [gmail] = box["mailboxes"]
    assert (gmail["address"], gmail["provider"], gmail["isDefault"]) == ("ria@getmeds.ph", "gmail", True)

    acme = company(client, crew["ria"])
    r = client.post("/email/send", json={"companyId": acme["id"], "to": ["buyer@acme.test"], "subject": "Onco One prices", "body": "Hello,\n\nAttached."}, headers=crew["ria"])
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "email" and r.json()["direction"] == "out"
    assert len(google) == 1 and google[0]["raw"]  # went out through Gmail
    on_page = client.get(f"/companies/{acme['id']}", headers=crew["ria"]).json()["activities"]
    assert [a["subject"] for a in on_page] == ["Onco One prices"]


def test_sending_needs_a_mailbox(client, crew):
    acme = company(client, crew["ria"])
    r = client.post("/email/send", json={"companyId": acme["id"], "to": ["a@b.test"], "subject": "x", "body": "y"}, headers=crew["ria"])
    assert r.status_code == 409 and "Connect your mailbox" in r.json()["detail"]


def test_any_provider_by_smtp(client, crew, monkeypatch):
    seen = {}

    class Server:
        def __init__(self, host, port, timeout=None):
            seen["host"] = host

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            seen["tls"] = True

        def login(self, user, password):
            if password != "right":
                raise mb.smtplib.SMTPAuthenticationError(535, b"no")
            seen["user"] = user

        def send_message(self, msg):
            seen["to"] = msg["To"]

    monkeypatch.setattr(mb.smtplib, "SMTP", Server)
    body = {"address": "ria@getmeds.ph", "host": "smtp.getmeds.ph", "port": 587, "security": "starttls", "username": "ria", "password": "wrong"}
    assert client.put("/mailbox/smtp", json=body, headers=crew["ria"]).status_code == 422
    ok = client.put("/mailbox/smtp", json={**body, "password": "right"}, headers=crew["ria"]).json()
    [box] = ok["mailboxes"]
    assert box["provider"] == "smtp" and seen["tls"]
    acme = company(client, crew["ria"])
    assert client.post("/email/send", json={"companyId": acme["id"], "to": ["buyer@acme.test"], "subject": "Hi", "body": "Hello"}, headers=crew["ria"]).status_code == 201
    assert seen["to"] == "buyer@acme.test"
    assert client.delete(f"/mailbox/{box['id']}", headers=crew["ria"]).status_code == 204
    assert client.get("/mailbox", headers=crew["ria"]).json()["mailboxes"] == []


def test_an_approved_email_keeps_its_wording(client, ana, crew, google):
    set_up_gmail(client, ana)
    url = client.post("/mailbox/start", json={"provider": "gmail"}, headers=crew["ria"]).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    client.post("/mailbox/finish", json={"state": state, "code": "c"}, headers=crew["ria"])
    t = client.post("/admin/email-templates", json={"name": "Intro", "subject": "Onco One for {customer}", "body": "Dear {contact},\n\nOnco One is now available.\n\n{me}", "approvedOn": "2026-01-01"}, headers=ana).json()
    assert [x["name"] for x in client.get("/email-templates", headers=crew["ria"]).json()] == ["Intro"]
    acme = company(client, crew["ria"], "Manila Cancer Center")
    sent = client.post("/email/send", json={"companyId": acme["id"], "to": ["md@mcc.test"], "templateId": t["id"], "note": "Good to see you today!", "subject": "Changed", "body": "Changed too"}, headers=crew["ria"]).json()
    # The template's own subject and wording, with the note on top: what the rep typed elsewhere is ignored.
    assert sent["subject"] == "Onco One for Manila Cancer Center"
    assert "Good to see you today!\n\nDear ,\n\nOnco One is now available." in sent["body"]
    # Out of date: not offered.
    client.put(f"/admin/email-templates/{t['id']}", json={"name": "Intro", "subject": "s", "body": "b", "approvedOn": "2026-01-01", "expiresOn": "2026-01-31"}, headers=ana)
    assert client.get("/email-templates", headers=crew["ria"]).json() == []


def test_several_mailboxes_and_choosing_from(client, ana, crew, google, monkeypatch):
    """Gmail and an SMTP mailbox side by side: each email goes from the one picked; the default otherwise."""
    set_up_gmail(client, ana)
    url = client.post("/mailbox/start", json={"provider": "gmail"}, headers=crew["ria"]).json()["url"]
    client.post("/mailbox/finish", json={"state": parse_qs(urlparse(url).query)["state"][0], "code": "c"}, headers=crew["ria"])

    sent_by_smtp = []

    class Server:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            sent_by_smtp.append(msg["From"])

    monkeypatch.setattr(mb.smtplib, "SMTP", Server)
    boxes = client.put("/mailbox/smtp", json={"address": "ria@zoho.example", "host": "smtp.zoho.example", "port": 587, "security": "starttls", "username": "ria", "password": "p"}, headers=crew["ria"]).json()["mailboxes"]
    gmail, other = boxes[0], boxes[1]
    assert (gmail["isDefault"], other["isDefault"]) == (True, False)
    acme = company(client, crew["ria"])
    send = lambda **extra: client.post("/email/send", json={"companyId": acme["id"], "to": ["b@acme.test"], "subject": "Hi", "body": "Hello", **extra}, headers=crew["ria"])
    assert send().status_code == 201 and len(google) == 1  # the default: Gmail
    picked = send(mailboxId=other["id"]).json()
    assert len(sent_by_smtp) == 1 and picked["body"].startswith("From ria@zoho.example (SMTP)")
    # Another person's mailbox can't be used.
    assert client.post("/email/send", json={"companyId": None, "to": ["b@acme.test"], "subject": "x", "body": "y", "mailboxId": other["id"]}, headers=crew["rex"]).status_code == 404
    # The default can change; the sent list has both.
    assert client.put(f"/mailbox/{other['id']}/default", headers=crew["ria"]).json()["mailboxes"][0]["id"] == other["id"]
    assert [e["subject"] for e in client.get("/emails", headers=crew["ria"]).json()["items"]] == ["Hi", "Hi"]
    assert client.get("/emails", headers=crew["rex"]).json()["total"] == 0


def test_one_field_works_out_what_connecting_takes(client, ana, monkeypatch):
    """Account → Mailbox asks only for the address first; the CRM works out the rest."""
    from app import mailbox

    monkeypatch.setattr(mailbox, "_by_mx", lambda domain: "google" if domain == "getmeds.ph" else None)
    gmail = client.get("/mailbox/detect", params={"address": "Ana@Gmail.com"}, headers=ana).json()
    assert gmail["address"] == "ana@gmail.com" and gmail["provider"] == "google" and gmail["smtp"]["host"] == "smtp.gmail.com"
    assert gmail["signIn"] is None and gmail["help"]["url"].startswith("https://")  # Google sign-in isn't set up here: an app password, with steps
    company = client.get("/mailbox/detect", params={"address": "ana@getmeds.ph"}, headers=ana).json()
    assert company["name"] == "Google" and not company["smtp"]["guessed"]
    other = client.get("/mailbox/detect", params={"address": "ana@example.org"}, headers=ana).json()
    assert other["provider"] is None and other["smtp"] == {"host": "smtp.example.org", "port": 587, "security": "starttls", "guessed": True}
    assert client.get("/mailbox/detect", params={"address": "not an email"}, headers=ana).status_code == 422


def test_a_company_domain_on_zoho_sends_through_zohos_business_server(client, ana, monkeypatch):
    from app import mailbox

    monkeypatch.setattr(mailbox, "_by_mx", lambda domain: "zoho_pro")
    found = client.get("/mailbox/detect", params={"address": "ana@getmeds.ph"}, headers=ana).json()
    assert found["name"] == "Zoho Mail" and found["smtp"]["host"] == "smtppro.zoho.com" and found["smtp"]["port"] == 465
    personal = client.get("/mailbox/detect", params={"address": "ana@zoho.com"}, headers=ana).json()
    assert personal["smtp"]["host"] == "smtp.zoho.com"
