"""AI output remains untrusted until reviewed by an authorized administrator."""
import json
import pytest
from sqlalchemy import select
from app.models import AuditEntry, AccessPolicyImport
from tests.test_company_access import modules, getmeds, person  # noqa: F401

ROOT = "/identity/access/policy"


def policy(client, getmeds):
    r = client.get(ROOT + "/context", headers=getmeds["owner"]["h"])
    assert r.status_code == 200, r.text
    c = r.json()
    return {"schemaVersion": 1, "status": "policy", "companyId": c["companyId"], "baseRevision": c["baseRevision"], "catalogRevision": c["catalogRevision"], "unresolved": [],
            "roles": [{"id": None, "name": "Reader", "description": None, "modules": [{"app": "crm", "scope": "own", "permissions": ["customers.view"]}], "abilities": []}]}


def validate(client, getmeds, d):
    return client.post(ROOT + "/validate", headers=getmeds["owner"]["h"], json={"response": json.dumps(d)})


def test_preview_confirmation_audit_and_immutable_version(client, getmeds, app):
    h = getmeds["owner"]["h"]
    original = client.get("/identity/access", headers=h).json()["roles"]
    draft = validate(client, getmeds, policy(client, getmeds))
    assert draft.status_code == 200, draft.text
    draft = draft.json()
    assert draft["valid"]
    assert client.get("/identity/access", headers=h).json()["roles"] == original
    url = ROOT + f"/{draft['id']}/apply"
    for confirmation in (False, 1, "true"):
        assert client.post(url, headers=h, json={"confirmed": confirmation}).status_code == 422
    r = client.post(url, headers=h, json={"confirmed": True})
    assert r.status_code == 200, r.text
    assert client.post(url, headers=h, json={"confirmed": True}).status_code == 409
    role = next(r for r in client.get("/identity/access", headers=h).json()["roles"] if r["name"] == "Reader")
    assert role["permissions"] == {"crm": ["customers.view"]} and role["scopes"] == {"crm": "own"}
    assert client.get(ROOT + "/history", headers=h).json()[0]["id"] == draft["id"]
    version = client.get(ROOT + "/history/" + draft["id"], headers=h).json()
    assert len(version["after"]) == len(version["before"]) + 1
    with app.state.sessions() as db:
        assert db.scalar(select(AuditEntry).where(AuditEntry.action == "access.policy_applied"))


@pytest.mark.parametrize("kind", ["permission", "app", "scope", "conditions", "role_twice", "app_twice", "permission_twice", "admin", "unresolved", "ability", "bool_version"])
def test_invalid_policies_fail_closed(client, getmeds, kind):
    d = policy(client, getmeds)
    role = d["roles"][0]
    if kind == "permission": role["modules"][0]["permissions"] = ["customers.approve"]
    if kind == "app": role["modules"][0]["app"] = "invented"
    if kind == "scope": role["modules"][0]["scope"] = None
    if kind == "conditions": role["conditions"] = {"amount": 100}
    if kind == "role_twice": d["roles"].append(role.copy())
    if kind == "app_twice": role["modules"].append(role["modules"][0].copy())
    if kind == "permission_twice": role["modules"][0]["permissions"] *= 2
    if kind == "admin": role["isAdmin"] = True
    if kind == "unresolved": d["unresolved"] = ["Who approves?"]
    if kind == "ability": role["abilities"] = [{"key": "discounts.approve", "limit": None}]
    if kind == "bool_version": d["schemaVersion"] = True
    r = validate(client, getmeds, d)
    assert r.status_code == 422 or (r.status_code == 200 and not r.json()["valid"]), r.text


def test_questions_and_duplicate_json_never_create_a_preview(client, getmeds):
    h = getmeds["owner"]["h"]
    r = validate(client, getmeds, {"status": "clarification", "questions": ["Who approves?"], "unsupported": []})
    assert not r.json()["valid"] and r.json()["clarification"]["questions"]
    r = client.post(ROOT + "/validate", headers=h, json={"response": '{"status":"policy","status":"clarification"}'})
    assert not r.json()["valid"]


def test_stale_and_expired_previews_are_rejected(client, getmeds, app):
    from datetime import UTC, datetime, timedelta
    h = getmeds["owner"]["h"]
    draft = validate(client, getmeds, policy(client, getmeds)).json()
    with app.state.sessions() as db:
        r = db.get(AccessPolicyImport, draft["id"])
        r.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.post(ROOT + f"/{draft['id']}/apply", headers=h, json={"confirmed": True}).status_code == 409
    draft = validate(client, getmeds, policy(client, getmeds)).json()
    assert client.post("/identity/access/roles", headers=h, json={"name": "Other"}).status_code == 201
    assert client.post(ROOT + f"/{draft['id']}/apply", headers=h, json={"confirmed": True}).status_code == 409


def test_export_and_replace_revoke_omitted_grants(client, getmeds):
    h = getmeds["owner"]["h"]
    made = client.post("/identity/access/roles", headers=h, json={"name": "Reader", "permissions": {"crm": ["customers.view", "customers.edit"], "pharmacy": ["prescriptions.view"]}, "scopes": {"crm": "all"}}).json()
    d = client.get(ROOT + "/export", headers=h).json()
    d["roles"] = [r for r in d["roles"] if r["id"] == made["id"]]
    assert validate(client, getmeds, d).json()["valid"]
    d["roles"][0]["modules"] = [{"app": "crm", "scope": "own", "permissions": ["customers.view"]}]
    preview = validate(client, getmeds, d).json()
    assert any(r["before"] and not r["after"] for r in preview["preview"]["roles"][0]["rows"])
    r = client.post(ROOT + f"/{preview['id']}/apply", headers=h, json={"confirmed": True})
    assert r.status_code == 200, r.text
    role = next(r for r in client.get("/identity/access", headers=h).json()["roles"] if r["id"] == made["id"])
    assert role["permissions"] == {"crm": ["customers.view"]}


def test_only_authorized_preview_owner_may_apply(client, getmeds, ana):
    jade = getmeds["jade"]["h"]
    d = policy(client, getmeds)
    preview = validate(client, getmeds, d).json()
    for path in ("/context", "/export", "/history"):
        assert client.get(ROOT + path, headers=jade).status_code == 403
    assert client.post(ROOT + "/validate", headers=jade, json={"response": json.dumps(d)}).status_code == 403
    second = person(client, ana, getmeds["company"], "Second", "second@getmeds.test", admin=True)
    assert client.post(ROOT + f"/{preview['id']}/apply", headers=second["h"], json={"confirmed": True}).status_code == 404
    d["companyId"] = "other-company"
    assert validate(client, getmeds, d).status_code == 403


def test_prompt_protocol_uses_supported_catalog(client, getmeds):
    r = client.post(ROOT + "/prompt", headers=getmeds["owner"]["h"], json={"requirements": "Let sales staff read their own customers only."})
    assert r.status_code == 200, r.text
    prompt = r.json()["prompt"]
    assert all(text in prompt for text in ("clarificationSchema", "customers.view", "CRUD never implies", "NEVER assume"))
