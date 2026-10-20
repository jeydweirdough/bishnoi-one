"""The lead inbox: the company's own channels call the CRM, signed with the
secret kept on the platform; what they send waits until someone adds it to the
customers or dismisses it."""

import hashlib
import hmac
import json

import pytest

from app import connections
from app.routers import inbox

SERVICES = {
    "facebook": {"page_id": "111", "app_secret": "fb-secret", "verify_token": "fb-verify", "page_access_token": "page-token"},
    "whatsapp": {"phone_number_id": "222", "app_secret": "wa-secret", "verify_token": "wa-verify"},
    "viber": {"auth_token": "viber-token"},
    "tawkto": {"webhook_secret": "tawk-secret"},
    "web_forms": {"form_key": "form-key-123"},
}


@pytest.fixture
def channels(monkeypatch):
    on = dict(SERVICES)
    monkeypatch.setattr(connections, "services", lambda settings, company=None: on)
    return on


def post(client, path, payload, header, secret, algo=hashlib.sha256, prefix=""):
    body = json.dumps(payload).encode()
    sig = prefix + hmac.new(secret.encode(), body, algo).hexdigest()
    return client.post(f"/hooks/{path}?company=getmeds", content=body, headers={header: sig, "Content-Type": "application/json"})


def whatsapp_message(text, mid, sender="639171234567"):
    return {"object": "whatsapp_business_account", "entry": [{"id": "x", "changes": [{"field": "messages", "value": {
        "metadata": {"phone_number_id": "222"}, "contacts": [{"profile": {"name": "Rose Pharmacy"}, "wa_id": sender}],
        "messages": [{"from": sender, "id": mid, "timestamp": "1760000000", "type": "text", "text": {"body": text}}]}}]}]}


def test_unsigned_calls_and_unconnected_channels_are_refused(client, channels):
    assert post(client, "whatsapp", whatsapp_message("hi", "m1"), "X-Hub-Signature-256", "wrong", prefix="sha256=").status_code == 401
    del channels["viber"]
    assert post(client, "viber", {"event": "message"}, "X-Viber-Content-Signature", "viber-token").status_code == 404
    r = client.get("/hooks/whatsapp?company=getmeds&hub.mode=subscribe&hub.verify_token=wa-verify&hub.challenge=42")
    assert r.status_code == 200 and r.text == "42"
    assert client.get("/hooks/whatsapp?company=getmeds&hub.mode=subscribe&hub.verify_token=nope&hub.challenge=42").status_code == 403


def test_messages_from_one_sender_wait_as_one_lead(client, ana, channels):
    for text, mid in (("Do you have amoxicillin?", "m1"), ("Do you have amoxicillin?", "m1"), ("And cetirizine", "m2")):
        assert post(client, "whatsapp", whatsapp_message(text, mid), "X-Hub-Signature-256", "wa-secret", prefix="sha256=").status_code == 200
    page = client.get("/inbox", headers=ana).json()
    assert page["counts"]["new"] == 1
    lead = page["items"][0]
    assert lead["name"] == "Rose Pharmacy" and lead["phone"] == "+639171234567" and lead["messageCount"] == 2 and lead["lastMessage"] == "And cetirizine"
    assert next(c for c in page["channels"] if c["key"] == "whatsapp")["address"].endswith("/hooks/whatsapp?company=getmeds")


def test_other_channels_come_in(client, ana, channels, monkeypatch):
    monkeypatch.setattr(inbox, "graph", lambda path, token, **p: {"field_data": [{"name": "full_name", "values": ["Lito Ramos"]}, {"name": "company_name", "values": ["Ramos Clinic"]}, {"name": "phone_number", "values": ["+639181112222"]}, {"name": "preferred_time", "values": ["Morning"]}]})
    fb = {"object": "page", "entry": [{"id": "111", "changes": [{"field": "leadgen", "value": {"leadgen_id": "L1", "form_id": "F1", "created_time": 1760000000}}]}]}
    assert post(client, "facebook", fb, "X-Hub-Signature-256", "fb-secret", prefix="sha256=").status_code == 200
    assert post(client, "facebook", fb, "X-Hub-Signature-256", "fb-secret", prefix="sha256=").status_code == 200  # sent again: kept once
    tawk = {"event": "chat:start", "chatId": "c1", "visitor": {"name": "Mae", "email": "mae@example.com", "city": "Cebu"}, "message": {"text": "Price of losartan?"}, "property": {"name": "getmeds.ph"}}
    assert post(client, "tawkto", tawk, "X-Tawk-Signature", "tawk-secret", algo=hashlib.sha1).status_code == 200
    viber = {"event": "message", "timestamp": 1760000000000, "message_token": 5, "sender": {"id": "v1", "name": "Jun"}, "message": {"type": "text", "text": "Hello"}}
    assert post(client, "viber", viber, "X-Viber-Content-Signature", "viber-token").status_code == 200
    assert client.post("/hooks/form?company=getmeds", json={"name": "Ana Lim", "pharmacy": "Lim Drugstore", "mobile": "0917 000 1111", "message": "Please call"}, headers={"X-Bishnoi-Key": "wrong"}).status_code == 401
    assert client.post("/hooks/form?company=getmeds", json={"name": "Ana Lim", "pharmacy": "Lim Drugstore", "mobile": "0917 000 1111", "message": "Please call"}, headers={"X-Bishnoi-Key": "form-key-123"}).status_code == 200
    items = {i["channel"]: i for i in client.get("/inbox", headers=ana).json()["items"]}
    assert set(items) == {"facebook", "tawkto", "viber", "form"}
    assert items["facebook"]["name"] == "Lito Ramos" and items["facebook"]["business"] == "Ramos Clinic"
    assert items["tawkto"]["email"] == "mae@example.com" and items["form"]["business"] == "Lim Drugstore"
    detail = client.get(f"/inbox/{items['facebook']['id']}", headers=ana).json()
    assert detail["details"]["Preferred time"] == "Morning"


def test_a_lead_becomes_a_customer_with_its_conversation(client, ana, ben, channels):
    post(client, "whatsapp", whatsapp_message("Do you deliver to Davao?", "m1"), "X-Hub-Signature-256", "wa-secret", prefix="sha256=")
    lead = client.get("/inbox", headers=ana).json()["items"][0]
    assert client.get("/inbox", headers=ben).status_code == 403  # a salesperson's role doesn't hold the inbox
    r = client.post(f"/inbox/{lead['id']}/add", json={"type": "customer"}, headers=ana)
    assert r.status_code == 200, r.text
    company = client.get(f"/companies/{r.json()['companyId']}", headers=ana).json()
    assert company["name"] == "Rose Pharmacy" and company["phone"] == "+639171234567"
    acts = client.get(f"/activities?company={company['id']}", headers=ana).json()["items"]
    assert any("Do you deliver to Davao?" in (a.get("body") or "") for a in acts) and any(a["subject"] == "Reply to Rose Pharmacy" for a in acts)
    assert client.post(f"/inbox/{lead['id']}/add", json={}, headers=ana).status_code == 409
    # A new message from them starts a new lead, which matches the customer already made.
    post(client, "whatsapp", whatsapp_message("Order again please", "m9"), "X-Hub-Signature-256", "wa-secret", prefix="sha256=")
    again = client.get("/inbox", headers=ana).json()["items"][0]
    assert client.get(f"/inbox/{again['id']}", headers=ana).json()["matches"][0]["id"] == company["id"]
    assert client.post(f"/inbox/{again['id']}/dismiss", headers=ana).json()["status"] == "dismissed"
    assert client.post(f"/inbox/{again['id']}/reopen", headers=ana).json()["status"] == "new"
