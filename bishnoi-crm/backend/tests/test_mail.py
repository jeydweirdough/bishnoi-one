"""Email notifications: who gets them, what they say, and that nothing is sent while off."""

import pytest

from app import mail
from tests.test_customers import company, crew  # noqa: F401  (crew is a fixture)
from tests.test_quotes import catalogue, ids, line, save  # noqa: F401  (fixtures)


@pytest.fixture
def outbox(app):
    mail.OUTBOX.clear()
    app.state.settings.email_enabled = True
    app.state.settings.crm_app_url = "https://crm.example.com/"
    yield mail.OUTBOX
    mail.OUTBOX.clear()


def waiting_quote(client, crew, ids) -> dict:
    acme = company(client, crew["ria"], "Acme Pharma")
    r = save(client, crew["ria"], acme, [line(ids["ORS-SACH"], 1, discount={"kind": "percent", "value": 1500})])
    assert r.status_code == 201, r.text
    return r.json()


def test_a_quote_waiting_for_approval_goes_to_the_teams_approvers(client, crew, ids, outbox):
    q = waiting_quote(client, crew, ids)
    assert len(outbox) == 1
    sent = outbox[0]
    # Lia leads Ria's team (North). Max reaches every team, but the team has its own approver.
    assert sent.to == ["lia@example.com"]
    assert sent.subject == f"Quote {q['number']} is waiting for your approval"
    assert "Ria made it for Acme Pharma." in sent.text
    assert "a discount above the limit" in sent.text
    assert f"https://crm.example.com/quotes/{q['id']}" in sent.html


def test_with_no_approver_in_the_team_those_over_every_team_get_it(client, crew, ids, outbox):
    acme = company(client, crew["sam"], "Beta Clinic")
    save(client, crew["sam"], acme, [line(ids["ORS-SACH"], 1, discount={"kind": "percent", "value": 1500})])
    # South has no team lead: the Director and the administrator hear of it.
    assert outbox[0].to == ["ana@example.com", "max@example.com"]


def test_the_rep_hears_the_decision_and_the_reason(client, crew, ids, outbox):
    q = waiting_quote(client, crew, ids)
    outbox.clear()
    assert client.post(f"/quotes/{q['id']}/approval", json={"decision": "reject", "note": "Too low for this customer"}, headers=crew["lia"]).status_code == 200
    assert [(m.to, m.subject) for m in outbox] == [(["ria@example.com"], f"Quote {q['number']} was rejected")]
    assert "Why: Too low for this customer" in outbox[0].text


def test_text_in_an_email_is_escaped(client, crew, ids, outbox):
    acme = company(client, crew["ria"], "<b>Acme</b> & Sons")
    save(client, crew["ria"], acme, [line(ids["ORS-SACH"], 1, discount={"kind": "percent", "value": 1500})])
    assert "&lt;b&gt;Acme&lt;/b&gt; &amp; Sons" in outbox[0].html and "<b>Acme</b>" not in outbox[0].html


def test_nothing_is_sent_while_email_is_off(app, client, crew, ids, outbox):
    app.state.settings.email_enabled = False
    waiting_quote(client, crew, ids)
    assert outbox == []
