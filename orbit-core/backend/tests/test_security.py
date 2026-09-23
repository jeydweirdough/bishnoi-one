"""The edges: rate limits, CORS, host names, security headers, and SQL injection."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.ratelimit import Buckets, Limit
from app.seed import DEMO_PASSWORD
from tests.conftest import build_app, customer_id


def login(client, who: str, **kw) -> dict:
    r = client.post("/auth/login", json={"email": f"{who}@pharmacrm.test", "password": DEMO_PASSWORD}, **kw)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def app_with(settings, records, files, **changes):
    return build_app(settings.model_copy(update=changes), records, files)


# --- rate limits -------------------------------------------------------------------------


def test_a_bucket_allows_a_burst_then_refills():
    buckets, limit = Buckets(), Limit(per_minute=60, burst=3)
    assert [buckets.take(("k",), limit, now=0)[0] for _ in range(4)] == [True, True, True, False]
    allowed, _, wait = buckets.take(("k",), limit, now=0)
    assert not allowed and wait == pytest.approx(1.0)  # one a second at 60 a minute
    assert buckets.take(("k",), limit, now=1.01)[0] is True
    assert buckets.take(("other",), limit, now=0)[0] is True  # every key has its own bucket


def test_each_person_has_their_own_limit(settings, records, files):
    app = app_with(settings, records, files, rate_limit_enabled=True, rate_reads_per_minute=30)  # a burst of 10
    with TestClient(app) as client:
        ana, ben = login(client, "ana"), login(client, "ben")
        codes = [client.get("/sales/customers?division=b2c", headers=ana).status_code for _ in range(11)]
        assert codes == [200] * 10 + [429]
        blocked = client.get("/sales/customers?division=b2c", headers=ana)
        assert int(blocked.headers["retry-after"]) >= 1 and "Try again in" in blocked.json()["detail"]
        # Ana using hers up doesn't slow Ben down.
        assert client.get("/sales/customers?division=b2c", headers=ben).status_code == 200
        assert client.get("/health").status_code == 200  # never limited


def test_writes_have_a_tighter_limit_than_reads(settings, records, files):
    app = app_with(settings, records, files, rate_limit_enabled=True, rate_writes_per_minute=10)  # a burst of 5
    with TestClient(app) as client:
        ana = login(client, "ana")
        maria = customer_id(client, ana, "b2c", "Maria Lopez")
        note = {"kind": "note", "summary": "Checking the limit"}
        codes = [client.post(f"/sales/customers/{maria}/activities", json=note, headers=ana).status_code for _ in range(6)]
        assert codes == [201] * 5 + [429]
        assert client.get(f"/sales/customers/{maria}", headers=ana).status_code == 200  # reads still fine


def test_sign_in_is_limited_by_the_real_client_address(settings, records, files):
    app = app_with(settings, records, files, rate_limit_enabled=True, rate_anonymous_per_minute=18)  # sign-in: a burst of 3
    wrong = lambda i: {"email": f"nobody{i}@pharmacrm.test", "password": "not it"}  # noqa: E731  (dodges the per-email limit)
    # Through the Next server (a trusted proxy), which passes on who's asking.
    with TestClient(app, client=("127.0.0.1", 5000)) as client:
        first = {"X-Forwarded-For": "203.0.113.5"}
        codes = [client.post("/auth/login", json=wrong(i), headers=first).status_code for i in range(4)]
        assert codes == [401, 401, 401, 429]
        assert client.post("/auth/login", json=wrong(9), headers={"X-Forwarded-For": "203.0.113.6"}).status_code == 401
        # No client address to go on: not limited by address, so one office can't lock out the rest.
        assert all(client.post("/auth/login", json=wrong(20 + i)).status_code == 401 for i in range(6))
    # From anywhere else, a forged X-Forwarded-For is ignored: the caller's own address counts.
    with TestClient(app, client=("198.51.100.7", 5000)) as client:
        codes = [client.post("/auth/login", json=wrong(40 + i), headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(4)]
        assert codes == [401, 401, 401, 429]


# --- CORS, hosts, headers --------------------------------------------------------------------


def test_no_other_site_can_call_the_api_from_a_browser(client):
    preflight = client.options(
        "/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert preflight.status_code == 400 and "access-control-allow-origin" not in preflight.headers
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_listed_origins_are_allowed_exactly(settings, records, files):
    app = app_with(settings, records, files, cors_origins=["https://crm.example.com"])
    with TestClient(app) as client:
        ok = client.options("/auth/login", headers={"Origin": "https://crm.example.com", "Access-Control-Request-Method": "POST"})
        assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "https://crm.example.com"
        other = client.options("/auth/login", headers={"Origin": "https://crm.example.com.evil.io", "Access-Control-Request-Method": "POST"})
        assert other.status_code == 400


@pytest.mark.parametrize("origin", ["*", "https://*.example.com", "crm.example.com", "https://crm.example.com/"])
def test_cors_origins_must_be_exact(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin])


def test_unknown_host_names_are_refused(client):
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 400


def test_every_response_carries_security_headers(client):
    for r in (client.get("/health"), client.get("/auth/me")):
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_production_hides_the_docs_and_pins_https(settings, records, files):
    prod = settings.model_copy(update={"environment": "production", "sanity_project_id": "p", "sanity_token": "t"})
    with TestClient(build_app(prod, records, files)) as client:
        assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404
        assert "max-age" in client.get("/health").headers["strict-transport-security"]


# --- SQL injection ------------------------------------------------------------------------------

PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE profiles; --",
    '" OR ""="',
    "1; DELETE FROM assignments",
    "Robert'); DROP TABLE local_credentials;--",
    '"] || true || ["',  # GROQ, for the records store
    "%",
    "_",
    "\\",
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_injection_payloads_are_just_text(client, as_, payload):
    ana, iris, carmen = as_("ana"), as_("iris"), as_("carmen")
    # Search boxes: nothing matches, nothing errors.
    r = client.get("/sales/customers", params={"division": "b2c", "q": payload}, headers=ana)
    assert r.status_code == 200
    r = client.get("/inventory/products", params={"q": payload}, headers=iris)
    assert r.status_code == 200 and r.json() == []  # % and _ don't act as wildcards either
    # Sign-in: a payload in the email or password is only a wrong password.
    r = client.post("/auth/login", json={"email": "ana@pharmacrm.test", "password": payload})
    assert r.status_code in (401, 422, 429)
    # Stored text comes back exactly as typed.
    r = client.post(
        "/admin/users",
        json={"email": f"p{abs(hash(payload))}@pharmacrm.test", "fullName": f"Test {payload}", "password": "long-enough-1"},
        headers=carmen,
    )
    assert r.status_code == 201 and r.json()["fullName"] == f"Test {payload}".strip()
    # Ids in the path: just ids that don't exist.
    assert client.get(f"/sales/customers/{payload}", headers=ana).status_code in (404, 405)
    # And everything is still there.
    assert len(client.get("/admin/users", headers=carmen).json()) >= 9
    assert client.post("/auth/login", json={"email": "ben@pharmacrm.test", "password": DEMO_PASSWORD}).status_code == 200


def test_no_sql_is_built_from_strings():
    """Every query goes through SQLAlchemy expressions, whose values are bound
    parameters. Raw SQL text (text(), exec_driver_sql, formatted execute) is how
    injection gets in, so none may appear in the app, apart from fixed PRAGMAs."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    risky = re.compile(r"\btext\(|exec_driver_sql|\.execute\(\s*f[\"']|\.execute\([^)]*(%|\.format\(|\+)")
    offenders = [
        f"{p.name}:{n}"
        for p in app_dir.rglob("*.py")
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if risky.search(line) and 'execute("PRAGMA' not in line
    ]
    assert offenders == []
