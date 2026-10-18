"""A Platform Admin deletes what was added: companies, applications, deployment
records, incidents, tickets and access requests. Support can't."""

from tests.conftest import app_id, make_company


def test_a_company_goes_with_its_people(client, ana, ben):
    c = make_company(client, ana, apps=("crm",))
    person = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Paolo", "email": "p@x.test"}, headers=ana).json()["user"]
    ticket = client.post("/platform/tickets", json={"kind": "bug", "title": "Page does not load", "companyId": c["id"], "reporterEmail": "p@x.test"}, headers=ana)
    assert client.delete(f"/platform/companies/{c['id']}", headers=ben).status_code == 403
    assert client.delete(f"/platform/companies/{c['id']}", headers=ana).status_code == 204
    assert client.get(f"/platform/companies/{c['id']}", headers=ana).status_code == 404
    assert client.get(f"/platform/users/{person['id']}", headers=ana).status_code == 404
    # The ticket it raised stays.
    if ticket.status_code == 201:
        assert client.get(f"/platform/tickets/{ticket.json()['ticket']['id']}", headers=ana).status_code == 200


def test_an_application_only_once_no_company_has_it(client, ana):
    made = client.post("/platform/applications", json={"key": "lab", "name": "Laboratory"}, headers=ana)
    assert made.status_code == 201, made.text
    lab = made.json()["application"]["id"]
    c = make_company(client, ana, apps=("crm",))
    client.put(f"/platform/companies/{c['id']}/applications", json={"applicationIds": [app_id(client, ana, "crm"), lab]}, headers=ana)
    r = client.delete(f"/platform/applications/{lab}", headers=ana)
    assert r.status_code == 409 and "Take it from them first" in r.json()["detail"]
    client.put(f"/platform/companies/{c['id']}/applications", json={"applicationIds": [app_id(client, ana, "crm")]}, headers=ana)
    assert client.delete(f"/platform/applications/{lab}", headers=ana).status_code == 204
    assert client.get(f"/platform/applications/{lab}", headers=ana).status_code == 404


def test_deployments_incidents_tickets_and_requests(client, ana, ben):
    crm = app_id(client, ana, "crm")
    client.post(f"/platform/applications/{crm}/deployments", json={"version": "9.9.9", "environment": "staging"}, headers=ana)
    d = next(x for x in client.get("/platform/deployments", headers=ana).json()["deployments"] if x["version"] == "9.9.9")
    assert client.delete(f"/platform/deployments/{d['id']}", headers=ana).status_code == 204
    assert all(x["version"] != "9.9.9" for x in client.get("/platform/deployments", headers=ana).json()["deployments"])

    incident = client.post("/platform/incidents", json={"title": "A little slow", "severity": "minor"}, headers=ana).json()["incident"]
    assert client.delete(f"/platform/incidents/{incident['id']}", headers=ben).status_code == 403
    assert client.delete(f"/platform/incidents/{incident['id']}", headers=ana).status_code == 204
    assert client.get(f"/platform/incidents/{incident['id']}", headers=ana).status_code == 404

    ticket = client.post("/platform/tickets", json={"kind": "bug", "title": "A test ticket", "reporterEmail": "x@y.test"}, headers=ben).json()["ticket"]
    assert client.delete(f"/platform/tickets/{ticket['id']}", headers=ana).status_code == 204
    assert client.get(f"/platform/tickets/{ticket['id']}", headers=ana).status_code == 404

    c = make_company(client, ana, apps=("crm",))
    person = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Paolo", "email": "p@x.test"}, headers=ana).json()["user"]
    req = client.post("/platform/access/requests", json={"identityId": person["id"], "applicationId": app_id(client, ana, "inventory")}, headers=ben).json()["request"]
    assert client.delete(f"/platform/access/requests/{req['id']}", headers=ana).status_code == 204
    assert client.get("/platform/access/requests", params={"status": "all"}, headers=ana).json()["requests"] == []
