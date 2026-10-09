"""A meeting's link (Google Meet, Zoom, Teams): kept on the meeting, shown with
a Join button; only web addresses are taken."""

from tests.test_customers import company


def test_a_meeting_keeps_its_link(client, ana):
    acme = company(client, ana, "Acme Hospital")
    r = client.post("/activities", json={"kind": "meeting", "subject": "Formulary review", "companyId": acme["id"], "meetingLink": "meet.google.com/abc-defg-hij"}, headers=ana)
    assert r.status_code == 201, r.text
    meeting = r.json()
    assert meeting["meetingLink"] == "https://meet.google.com/abc-defg-hij"  # the https:// is added

    r = client.patch(f"/activities/{meeting['id']}", json={"meetingLink": "https://zoom.us/j/123456789"}, headers=ana)
    assert r.status_code == 200 and r.json()["meetingLink"] == "https://zoom.us/j/123456789"
    r = client.patch(f"/activities/{meeting['id']}", json={"meetingLink": ""}, headers=ana)
    assert r.status_code == 200 and r.json()["meetingLink"] is None  # cleared


def test_only_a_web_address_is_taken(client, ana):
    for bad in ("javascript:alert(1)", "ftp://files.example.com/x", "not a link at all"):
        r = client.post("/activities", json={"kind": "meeting", "subject": "x", "meetingLink": bad}, headers=ana)
        assert r.status_code == 422, (bad, r.text)
    # A note has no meeting to join: a link sent with one isn't kept.
    r = client.post("/activities", json={"kind": "note", "subject": "x", "meetingLink": "https://zoom.us/j/1"}, headers=ana)
    assert r.status_code == 201 and r.json()["meetingLink"] is None
