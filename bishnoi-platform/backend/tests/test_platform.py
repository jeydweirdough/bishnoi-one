"""Companies, applications, users and their access, support, incidents,
monitoring, communications, settings and the dashboard."""

from app import monitor
from tests.conftest import app_id, make_company


# ---- Organizations ---------------------------------------------------------------


def test_add_a_company_with_its_admin_and_apps(client, ana):
    c = make_company(client, ana, adminName="Jade Madigal", adminEmail="Jade@GetMeds.test")
    assert c["slug"] == "getmeds" and c["appCount"] == 2 and c["userCount"] == 1
    detail = client.get(f"/platform/companies/{c['id']}", headers=ana).json()["company"]
    assert [a["key"] for a in detail["applications"]] == ["crm", "pharmacy"]
    assert detail["admins"][0]["email"] == "jade@getmeds.test"
    again = client.post("/platform/companies", json={"name": "GetMeds"}, headers=ana)
    assert again.status_code == 422 and "taken" in again.text


def test_departments_and_branches(client, ana):
    c = make_company(client, ana)
    r = client.post(f"/platform/companies/{c['id']}/units", json={"kind": "branch", "name": "Cebu", "location": "Cebu City"}, headers=ana)
    assert r.status_code == 201
    unit = r.json()["unit"]
    assert client.post(f"/platform/companies/{c['id']}/units", json={"kind": "branch", "name": "cebu"}, headers=ana).status_code == 422
    assert client.post(f"/platform/companies/{c['id']}/units", json={"kind": "department", "name": "Cebu"}, headers=ana).status_code == 201
    client.patch(f"/platform/companies/{c['id']}/units/{unit['id']}", json={"name": "Cebu North"}, headers=ana)
    units = client.get(f"/platform/companies/{c['id']}", headers=ana).json()["company"]["units"]
    assert {(u["kind"], u["name"]) for u in units} == {("branch", "Cebu North"), ("department", "Cebu")}
    assert client.delete(f"/platform/companies/{c['id']}/units/{unit['id']}", headers=ana).status_code == 204


def test_suspending_a_company_is_logged(client, ana):
    c = make_company(client, ana)
    r = client.patch(f"/platform/companies/{c['id']}", json={"status": "suspended"}, headers=ana)
    assert r.json()["company"]["status"] == "suspended" and r.json()["company"]["suspendedAt"]
    log = client.get(f"/platform/activity?company_id={c['id']}", headers=ana).json()["entries"]
    assert log[0]["action"] == "company.suspended"


# ---- Users and access ------------------------------------------------------------


def test_access_never_goes_past_the_company(client, ana):
    c = make_company(client, ana, apps=("crm",))
    crm, pharmacy = app_id(client, ana, "crm"), app_id(client, ana, "pharmacy")
    r = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Maria Santos", "email": "maria@x.test",
                                             "applications": [{"applicationId": pharmacy}]}, headers=ana)
    assert r.status_code == 422 and "doesn't have" in r.text
    r = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Maria Santos", "email": "maria@x.test",
                                             "applications": [{"applicationId": crm, "role": "Salesperson"}]}, headers=ana)
    person = r.json()["user"]
    assert client.put(f"/platform/users/{person['id']}/applications/{pharmacy}", json={}, headers=ana).status_code == 422
    # The company loses the CRM, and so does she.
    r = client.put(f"/platform/companies/{c['id']}/applications", json={"applicationIds": []}, headers=ana)
    assert r.json() == {"added": 0, "removed": 1, "withdrawnFromPeople": 1}
    assert client.get(f"/platform/users/{person['id']}", headers=ana).json()["user"]["applications"] == []


def test_grants_roles_and_app_admins(client, ana):
    c = make_company(client, ana)
    crm = app_id(client, ana, "crm")
    person = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Jade", "email": "jade@x.test"}, headers=ana).json()["user"]
    r = client.put(f"/platform/users/{person['id']}/applications/{crm}", json={"role": "Administrator", "isAppAdmin": True}, headers=ana)
    assert r.json()["grant"]["isAppAdmin"] is True
    detail = client.get(f"/platform/users/{person['id']}", headers=ana).json()["user"]
    assert [g["name"] for g in detail["applications"]] == ["CRM"]
    assert [a["key"] for a in detail["canBeGiven"]] == ["pharmacy"]
    assert detail["activity"][0]["action"] == "access.granted"
    matrix = client.get("/platform/access/organizations", headers=ana).json()
    row = matrix["companies"][0]
    crm_cell = next(cell for cell in row["cells"] if cell["applicationId"] == crm)
    assert crm_cell == {"applicationId": crm, "enabled": True, "userCount": 1}
    apps = client.get("/platform/access/applications", headers=ana).json()["applications"]
    assert next(a for a in apps if a["id"] == crm)["admins"][0]["name"] == "Jade"
    assert client.delete(f"/platform/users/{person['id']}/applications/{crm}", headers=ana).status_code == 204


def test_access_requests(client, ana, ben):
    c = make_company(client, ana, apps=("crm",))
    crm, inventory = app_id(client, ana, "crm"), app_id(client, ana, "inventory")
    person = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Paolo", "email": "p@x.test"}, headers=ana).json()["user"]
    # Support logs it; a Platform Admin decides.
    r = client.post("/platform/access/requests", json={"identityId": person["id"], "applicationId": inventory, "role": "Viewer"}, headers=ben)
    assert r.status_code == 201 and r.json()["request"]["companyHasApp"] is False
    req = r.json()["request"]
    assert client.post("/platform/access/requests", json={"identityId": person["id"], "applicationId": inventory}, headers=ben).status_code == 409
    assert client.post(f"/platform/access/requests/{req['id']}/decision", json={"approve": True}, headers=ben).status_code == 403
    assert client.post(f"/platform/access/requests/{req['id']}/decision", json={"approve": True}, headers=ana).status_code == 409
    client.put(f"/platform/companies/{c['id']}/applications", json={"applicationIds": [crm, inventory]}, headers=ana)
    r = client.post(f"/platform/access/requests/{req['id']}/decision", json={"approve": True}, headers=ana)
    assert r.json()["request"]["status"] == "approved"
    grants = client.get(f"/platform/users/{person['id']}", headers=ana).json()["user"]["applications"]
    assert grants[0]["role"] == "Viewer"
    assert client.get("/platform/access/requests", headers=ana).json()["pending"] == 0


def test_moving_a_person_keeps_only_what_the_new_company_has(client, ana):
    a = make_company(client, ana, "A Co", apps=("crm", "pharmacy"))
    b = make_company(client, ana, "B Co", apps=("crm",))
    crm, pharmacy = app_id(client, ana, "crm"), app_id(client, ana, "pharmacy")
    person = client.post("/platform/users", json={"companyId": a["id"], "fullName": "Mo", "email": "mo@x.test",
                                                  "applications": [{"applicationId": crm}, {"applicationId": pharmacy}]}, headers=ana).json()["user"]
    r = client.patch(f"/platform/users/{person['id']}", json={"companyId": b["id"]}, headers=ana)
    assert r.json()["withdrawnApplications"] == 1
    listed = client.get(f"/platform/users?company_id={b['id']}", headers=ana).json()["users"]
    assert [x["name"] for x in listed[0]["applications"]] == ["CRM"]


# ---- Applications and monitoring -------------------------------------------------


def test_registry_is_seeded_and_checked(client, ana, probes):
    apps = client.get("/platform/applications", headers=ana).json()["applications"]
    assert {a["key"] for a in apps} >= {"platform", "crm", "inventory", "pharmacy"}
    assert all(a["status"] == "operational" for a in apps)
    assert all(a["lastCheck"]["ms"] == 12 for a in apps)


def test_status_comes_from_the_check_unless_declared(client, ana, probes):
    crm = next(a for a in client.get("/platform/applications", headers=ana).json()["applications"] if a["key"] == "crm")
    probes[crm["healthUrl"]] = monitor.Answer("down", None, None, "Not answering.")
    health = client.get("/platform/monitoring?refresh=true", headers=ana).json()
    assert next(a for a in health["applications"] if a["key"] == "crm")["status"] == "down"
    assert health["overall"] == "down"
    r = client.patch(f"/platform/applications/{crm['id']}", json={"statusOverride": "maintenance", "statusNote": "Upgrading"}, headers=ana)
    assert r.json()["application"]["status"] == "maintenance"
    r = client.patch(f"/platform/applications/{crm['id']}", json={"statusOverride": None}, headers=ana)
    assert r.json()["application"]["status"] == "down" and r.json()["application"]["statusNote"] is None


def test_a_starting_app_that_cannot_says_why(monkeypatch):
    class Reply:
        status_code = 503

        def json(self):
            return {"ok": False, "problem": "database", "check": ["DATABASE_URL"]}

    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: Reply())
    answer = monitor.probe("http://x.test/health", 3, 1500)
    assert answer.status == "down" and "DATABASE_URL" in answer.detail


def test_deployments_set_the_version(client, ana):
    crm = app_id(client, ana, "crm")
    client.post(f"/platform/applications/{crm}/deployments", json={"version": "0.2.0", "environment": "staging"}, headers=ana)
    detail = client.get(f"/platform/applications/{crm}", headers=ana).json()["application"]
    assert detail["version"] == "0.1.0"
    client.post(f"/platform/applications/{crm}/deployments", json={"version": "0.2.0"}, headers=ana)
    detail = client.get(f"/platform/applications/{crm}", headers=ana).json()["application"]
    assert detail["version"] == "0.2.0" and len(detail["deployments"]) == 2
    assert len(client.get("/platform/deployments", headers=ana).json()["deployments"]) == 2


def test_integrations_with_an_address_are_checked(client, ana, probes):
    crm = app_id(client, ana, "crm")
    probes["https://pay.test/health"] = monitor.Answer("degraded", 2400, 200, "Slow: 2400 ms to answer.")
    r = client.post(f"/platform/applications/{crm}/integrations",
                    json={"name": "Payments", "target": "PayMongo", "healthUrl": "https://pay.test/health"}, headers=ana)
    assert r.status_code == 201
    client.get("/platform/monitoring?refresh=true", headers=ana)
    links = client.get("/platform/integrations", headers=ana).json()["integrations"]
    assert links[0]["status"] == "degraded" and links[0]["lastCheck"]["ms"] == 2400
    bad = client.post(f"/platform/applications/{crm}/integrations", json={"name": "X", "healthUrl": "file:///etc/passwd"}, headers=ana)
    assert bad.status_code == 422


def test_traffic_counts_the_platforms_requests(client, ana):
    for _ in range(3):
        client.get("/platform/companies", headers=ana)
    client.get("/platform/companies/nope", headers=ana)
    t = client.get("/platform/traffic?hours=1", headers=ana).json()
    assert t["summary"]["requests"] >= 5 and t["summary"]["refused"] >= 1
    assert t["series"] and t["applicationResponse"]


# ---- Support and incidents -------------------------------------------------------


def test_ticket_lifecycle(client, ana, ben):
    c = make_company(client, ana)
    pharmacy = app_id(client, ana, "pharmacy")
    r = client.post("/platform/tickets", json={"kind": "bug", "title": "Dispensing page does not load", "severity": "high",
                                               "companyId": c["id"], "applicationId": pharmacy, "reporterName": "Maria Santos"}, headers=ben)
    assert r.status_code == 201, r.text
    t = r.json()["ticket"]
    assert t["number"].startswith("BUG-") and t["number"].endswith("-00001") and t["status"] == "reported"
    staff = client.get("/platform/staff", headers=ben).json()["staff"]
    ben_id = next(s["id"] for s in staff if s["email"] == "ben@example.com")
    t = client.patch(f"/platform/tickets/{t['id']}", json={"assigneeId": ben_id}, headers=ben).json()["ticket"]
    assert t["status"] == "assigned"
    t = client.patch(f"/platform/tickets/{t['id']}", json={"status": "resolved", "note": "Index added."}, headers=ben).json()["ticket"]
    assert t["resolvedAt"] and not t["isOpen"]
    assert [(n["from"], n["to"]) for n in t["notes"] if n["to"]][-2:] == [("reported", "assigned"), ("assigned", "resolved")]
    assert t["notes"][-1]["body"] == "Index added."
    t = client.patch(f"/platform/tickets/{t['id']}", json={"status": "investigating"}, headers=ben).json()["ticket"]
    assert t["resolvedAt"] is None
    second = client.post("/platform/tickets", json={"kind": "bug", "title": "Another one", "reporterEmail": "x@y.test"}, headers=ben)
    assert second.json()["ticket"]["number"].endswith("-00002")
    nobody = client.post("/platform/tickets", json={"kind": "complaint", "title": "Who said it?"}, headers=ben)
    assert nobody.status_code == 422


def test_overdue_follows_the_response_targets(client, ana):
    r = client.post("/platform/tickets", json={"kind": "bug", "title": "Broken", "severity": "critical", "reporterName": "Mo"}, headers=ana)
    assert r.json()["ticket"]["isOverdue"] is False
    from app.models import Ticket
    from datetime import UTC, datetime, timedelta

    with client.app.state.sessions() as db:
        db.get(Ticket, r.json()["ticket"]["id"]).created_at = datetime.now(UTC) - timedelta(hours=5)
        db.commit()
    listed = client.get("/platform/tickets?kind=bug", headers=ana).json()
    assert listed["tickets"][0]["isOverdue"] is True and listed["openByKind"] == {"bug": 1}
    assert client.get("/platform/dashboard", headers=ana).json()["support"]["overdue"] == 1


def test_incident_from_declared_to_resolved(client, ana, ben):
    c = make_company(client, ana)
    pharmacy = app_id(client, ana, "pharmacy")
    r = client.post("/platform/incidents", json={"title": "Pharmacy is down", "severity": "critical", "kind": "application",
                                                 "applicationId": pharmacy, "companyIds": [c["id"]], "update": "Looking."}, headers=ben)
    assert r.status_code == 201, r.text
    i = r.json()["incident"]
    assert i["number"].endswith("-0001") and i["companies"][0]["name"] == "GetMeds"
    assert client.get("/platform/banner", headers=ben).json()["incidents"][0]["id"] == i["id"]
    detail = client.get(f"/platform/companies/{c['id']}", headers=ana).json()["company"]
    assert detail["activeIncidents"][0]["number"] == i["number"]
    i = client.post(f"/platform/incidents/{i['id']}/updates", json={"status": "resolved", "body": "Back up."}, headers=ben).json()["incident"]
    assert i["resolvedAt"] and not i["isActive"] and [u["status"] for u in i["updates"]] == ["resolved", "investigating"]
    assert client.get("/platform/incidents", headers=ben).json()["active"] == 0
    assert len(client.get("/platform/incidents?state=resolved", headers=ben).json()["incidents"]) == 1


def test_a_minor_incident_stays_off_the_banner_unless_asked(client, ana):
    client.post("/platform/incidents", json={"title": "A little slow", "severity": "minor"}, headers=ana)
    assert client.get("/platform/banner", headers=ana).json()["incidents"] == []
    notifications = client.get("/platform/settings", headers=ana).json()["settings"]["notifications"]
    client.put("/platform/settings/notifications", json={**notifications, "bannerSeverity": "minor"}, headers=ana)
    assert len(client.get("/platform/banner", headers=ana).json()["incidents"]) == 1


# ---- Communications, settings, dashboard -----------------------------------------


def test_notices_and_what_apps_read(client, ana, ben):
    c = make_company(client, ana)
    crm = app_id(client, ana, "crm")
    assert client.post("/platform/announcements", json={"title": "Hello all"}, headers=ben).status_code == 403
    r = client.post("/platform/announcements", json={"kind": "maintenance", "title": "Upgrade"}, headers=ana)
    assert r.status_code == 422
    draft = client.post("/platform/announcements", json={"title": "CRM for GetMeds", "applicationId": crm, "companyId": c["id"]},
                        headers=ana).json()["notice"]
    assert draft["state"] == "draft"
    assert client.get("/public/notices?app=crm&company=getmeds").json()["notices"] == []
    client.patch(f"/platform/announcements/{draft['id']}", json={"publish": True}, headers=ana)
    assert [n["title"] for n in client.get("/public/notices?app=crm&company=getmeds").json()["notices"]] == ["CRM for GetMeds"]
    assert client.get("/public/notices?app=inventory&company=getmeds").json()["notices"] == []
    assert client.get("/public/notices?app=crm").json()["notices"] == []


def test_settings_are_checked_and_logged(client, ana, ben):
    s = client.get("/platform/settings", headers=ben).json()["settings"]
    assert s["security"]["sessionHours"] == 10 and s["notifications"]["responseHours"]["critical"] == 4
    assert client.put("/platform/settings/monitoring", json={**s["monitoring"], "staleSeconds": 5}, headers=ana).status_code == 422
    assert client.put("/platform/settings/monitoring", json=s["monitoring"], headers=ben).status_code == 403
    r = client.put("/platform/settings/platform", json={**s["platform"], "supportEmail": "help@bishnoi.test"}, headers=ana)
    assert r.json()["settings"]["platform"]["supportEmail"] == "help@bishnoi.test"
    log = client.get("/platform/activity", headers=ana).json()["entries"]
    assert log[0]["action"] == "settings.platform" and log[0]["fields"] == ["supportEmail"]


def test_dashboard(client, ana):
    make_company(client, ana, adminName="Jade", adminEmail="jade@x.test")
    d = client.get("/platform/dashboard", headers=ana).json()
    assert d["counts"]["companies"] == 1 and d["counts"]["users"] == 1 and d["counts"]["applications"] == 8
    assert d["health"]["overall"] == "operational" and d["health"]["database"]["status"] == "operational"
    assert d["recent"][0]["action"] == "user.created"
    options = client.get("/platform/options", headers=ana).json()
    assert len(options["applications"]) == 8 and len(options["staff"]) == 2
