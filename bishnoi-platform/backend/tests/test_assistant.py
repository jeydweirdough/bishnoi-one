"""The assistant can plan reads, but cannot choose identity, authority or SQL."""
import json
import pytest
import httpx
from sqlalchemy import select
from app import assistant
from app.models import Identity, AccessRole, AccessRoleAbility, AuditEntry, Company, CompanyApp, Application
from tests.test_company_access import modules, getmeds, person  # noqa: F401
from tests.conftest import make_company

URL = "/identity/assistant/chat"


def send(client, getmeds, who="owner", message="Who is our CEO?", **extra):
    return client.post(URL, headers=getmeds[who]["h"], json={"companyId": getmeds["company"]["id"], "message": message, **extra})


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def configured(app, monkeypatch):
    app.state.settings.ollama_base_url = "http://ollama:11434"
    async def choose(*args):
        return assistant.Plan(tool="directory", query="CEO", month=None)
    monkeypatch.setattr(assistant, "plan", choose)


def test_signed_in_active_company_required(client, getmeds, configured):
    assert client.post(URL, json={"companyId": getmeds["company"]["id"], "message": "Who is CEO?"}).status_code == 401
    r = client.post(URL, headers=getmeds["owner"]["h"], json={"companyId": "different-company", "message": "Who is CEO?"})
    assert r.status_code == 409
    assert send(client, getmeds, message=" ").status_code == 422


def test_directory_has_no_cross_company_or_deleted_employees(client, getmeds, configured, app):
    from datetime import UTC, datetime
    with app.state.sessions() as db:
        other = Company(name="Other company", slug="other-company")
        db.add(other); db.flush()
        db.add(Identity(company_id=other.id, email="other@example.test", full_name="Other company CEO", title="CEO"))
        jade = db.get(Identity, getmeds["jade"]["id"])
        jade.title = "Chief Executive Officer"
        rio = db.get(Identity, getmeds["rio"]["id"])
        rio.title, rio.deleted_at = "CEO", datetime.now(UTC)
        db.add(Identity(company_id=getmeds["company"]["id"], email="operator@example.test", full_name="Hidden Operator", title="CEO", via_operator=True))
        db.commit()
    r = send(client, getmeds)
    assert r.status_code == 200, r.text
    got = events(r)
    answer = "".join(e.get("text", "") for e in got)
    assert "Jade Madigal" in answer and "Rio Santos" not in answer and "Hidden Operator" not in answer and "Other company CEO" not in answer
    assert got[-1]["type"] == "done" and any(e["type"] == "sources" for e in got)
    with app.state.sessions() as db:
        assert db.scalar(select(AuditEntry).where(AuditEntry.action == "assistant.completed"))


def test_directory_denied_until_explicit_ability(client, getmeds, configured, app):
    got = events(send(client, getmeds, who="jade"))
    assert any(e["type"] == "error" and "directory" in e["message"] for e in got)
    with app.state.sessions() as db:
        role = AccessRole(company_id=getmeds["company"]["id"], name="Directory reader")
        db.add(role); db.flush()
        db.add(AccessRoleAbility(role_id=role.id, ability="directory.read", limit_value=None))
        db.get(Identity, getmeds["jade"]["id"]).access_role_id = role.id
        db.commit()
    got = events(send(client, getmeds, who="jade"))
    assert got[-1]["type"] == "done"
    assert "No active employee" in "".join(e.get("text", "") for e in got)


def test_missing_record_is_not_inferred_from_seniority(client, getmeds, configured, app):
    with app.state.sessions() as db:
        db.get(Identity, getmeds["jade"]["id"]).title = "President"
        db.get(Identity, getmeds["rio"]["id"]).title = "Assistant to CEO"
        db.commit()
    got = events(send(client, getmeds))
    assert "cannot infer" in "".join(e.get("text", "") for e in got)


def test_finance_permission_denied_before_network(client, getmeds, configured, monkeypatch):
    async def choose(*args): return assistant.Plan(tool="finance", query=None, month="2026-10")
    async def never(*args): raise AssertionError("unauthorized network request")
    monkeypatch.setattr(assistant, "plan", choose)
    monkeypatch.setattr(assistant, "finance", never)
    got = events(send(client, getmeds, who="jade"))
    assert any(e["type"] == "error" and "Finance access" in e["message"] for e in got)


def test_planner_errors_and_timeouts_fail_safely(client, getmeds, configured, monkeypatch):
    async def timed_out(*args): raise httpx.ReadTimeout("private-url-or-secret")
    monkeypatch.setattr(assistant, "plan", timed_out)
    r = send(client, getmeds)
    assert "private-url-or-secret" not in r.text and "timed out" in r.text
    # Slot is released on failure, so a subsequent request is accepted.
    assert send(client, getmeds).status_code == 200


def test_model_disabled_and_busy_states(client, getmeds, app, configured):
    app.state.settings.ollama_base_url = None
    assert send(client, getmeds).status_code == 503
    app.state.settings.ollama_base_url = "http://ollama:11434"
    key = (getmeds["owner"]["id"], getmeds["company"]["id"])
    assistant.enter(key)
    try: assert send(client, getmeds).status_code == 429
    finally: assistant.leave(key)


def test_ollama_payload_is_bounded_non_thinking_and_schema_constrained(monkeypatch):
    import asyncio
    from app.config import Settings
    payloads = []
    class Reply:
        status_code = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def aiter_bytes(self):
            yield json.dumps({"message": {"content": '{"tool":"finance","query":null,"month":"2026-10"}', "thinking": "never exposed"}}).encode()
    class Client:
        def __init__(self, **kwargs): assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def stream(self, method, url, json): payloads.append(json); return Reply()
    async def private(*args): pass
    monkeypatch.setattr(assistant, "ensure_private_ollama", private)
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    settings = Settings(_env_file=None, ollama_base_url="http://ollama:11434")
    body = assistant.ChatIn(companyId="company", message="Show October 2026 financials")
    result = asyncio.run(assistant.plan(body, settings, "2026-11-03"))
    assert result.month == "2026-10"
    sent = payloads[0]
    assert sent["model"] == "qwen3:1.7b" and sent["think"] is False
    assert sent["options"]["num_predict"] <= 256 and sent["format"]["additionalProperties"] is False
    with pytest.raises(Exception): assistant.Plan(tool="sql", query="SELECT *", month=None)


def test_authorized_finance_uses_scoped_short_lived_pass(client, getmeds, configured, app, monkeypatch):
    from app.passes import claims_of
    with app.state.sessions() as db:
        finance = db.scalar(select(Application).where(Application.key == "finance"))
        finance.api_url = "http://finance-internal:8303"
        db.add(CompanyApp(company_id=getmeds["company"]["id"], application_id=finance.id))
        db.commit()
    async def choose(*args): return assistant.Plan(tool="finance", query=None, month="2026-10")
    async def check(base, token, month, company_id):
        claims = claims_of(token)
        assert base == "http://finance-internal:8303" and month == "2026-10"
        assert claims["kind"] == "assistant-read" and claims["tool"] == "monthly-summary"
        assert claims["company"] == getmeds["company"]["id"] == company_id
        assert claims["exp"] - claims["iat"] == 60
        return {"answer": "Verified monthly result", "sources": []}
    monkeypatch.setattr(assistant, "plan", choose)
    monkeypatch.setattr(assistant, "finance", check)
    assert events(send(client, getmeds))[-1]["type"] == "done"


def test_foreign_finance_response_is_never_rendered(monkeypatch):
    import asyncio
    real = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"companyId": "different"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=transport, **kwargs))
    with pytest.raises(Exception) as e:
        asyncio.run(assistant.finance("http://finance", "token", "2026-10", "current-company"))
    assert e.value.status_code == 403


def test_public_ollama_address_is_refused():
    import asyncio
    with pytest.raises(Exception) as e:
        asyncio.run(assistant.ensure_private_ollama("http://8.8.8.8:11434"))
    assert e.value.status_code == 503
