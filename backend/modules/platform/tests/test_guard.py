"""The guard (app/guard.py): limits, sizes, and errors that say nothing about the insides.

On a small app of its own, so the same tests stand in every app's API."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from modules.platform.guard import install


@pytest.fixture
def guarded(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("RATE_LIMIT_WRITES_PER_MINUTE", "2")
    monkeypatch.setenv("RATE_LIMIT_ANONYMOUS_PER_MINUTE", "3")
    monkeypatch.setenv("MAX_REQUEST_MB", "1")
    app = FastAPI()
    install(app, "Test")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/thing")
    def thing() -> dict:
        return {"ok": True}

    @app.post("/thing")
    async def save(request: Request) -> dict:
        return {"size": len(await request.body())}

    @app.get("/broken")
    def broken() -> dict:
        raise RuntimeError("password=hunter2 at /srv/app/secret.py")

    @app.get("/database")
    def database() -> dict:
        raise OperationalError("SELECT 1", {}, Exception("server at 10.0.0.5 closed the connection"))

    return TestClient(app, raise_server_exceptions=False)


SIGNED_IN = {"Authorization": "Bearer " + "x" * 40}


def test_too_many_requests_wait_their_turn_and_are_told_how_long(guarded):
    for _ in range(3):
        assert guarded.get("/thing").status_code == 200
    r = guarded.get("/thing")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert "Wait" in r.json()["detail"] and r.json()["reference"]
    # Someone signed in is counted on their own, with a bigger allowance.
    for _ in range(5):
        assert guarded.get("/thing", headers=SIGNED_IN).status_code == 200
    assert guarded.get("/thing", headers=SIGNED_IN).status_code == 429
    # The host's health check is never turned away.
    assert all(guarded.get("/health").status_code == 200 for _ in range(10))


def test_saves_have_a_tighter_limit(guarded):
    other = {"Authorization": "Bearer " + "y" * 40}
    assert [guarded.post("/thing", content=b"a", headers=other).status_code for _ in range(3)] == [200, 200, 429]


def test_something_too_big_is_refused_before_it_is_read(guarded):
    r = guarded.post("/thing", content=b"x" * (1024 * 1024 + 1), headers=SIGNED_IN)
    assert r.status_code == 413 and "1 MB" in r.json()["detail"]


def test_an_unplanned_error_says_nothing_about_the_insides(guarded):
    r = guarded.get("/broken", headers=SIGNED_IN)
    body = r.text
    assert r.status_code == 500 and "Something went wrong on our side" in body
    assert "hunter2" not in body and "secret.py" not in body and "RuntimeError" not in body
    # The reference it gives is the one on the response, for the log.
    assert r.json()["reference"] in body and r.headers["x-request-id"] == r.json()["reference"]


def test_a_database_that_is_away_is_a_wait_not_a_fault(guarded):
    r = guarded.get("/database", headers=SIGNED_IN)
    assert r.status_code == 503 and r.headers["retry-after"] == "5"
    assert "isn't answering" in r.json()["detail"] and "10.0.0.5" not in r.text


def test_every_answer_has_a_reference(guarded):
    assert len(guarded.get("/thing", headers=SIGNED_IN).headers["x-request-id"]) >= 8


def _app(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    app = FastAPI()
    install(app, "Test")

    @app.get("/thing")
    def thing(request: Request) -> dict:
        from modules.platform.guard import address_of

        return {"address": address_of(request)}

    @app.post("/identity/login")
    def login() -> dict:
        return {"ok": True}

    return app


def test_a_forwarded_address_counts_only_from_a_proxy_we_trust(monkeypatch):
    # The test client's connection is "testclient": trusted, like the one app on our own network.
    app = _app(monkeypatch, RATE_LIMIT_ANONYMOUS_PER_MINUTE="2")
    near = TestClient(app, client=("10.0.1.5", 5000))
    assert near.get("/thing", headers={"X-Forwarded-For": "203.0.113.9"}).json()["address"] == "203.0.113.9"
    # From outside our network the header is ignored: the connection's own address counts, so faking it gains nothing.
    far = TestClient(app, client=("198.51.100.7", 5000))
    assert far.get("/thing", headers={"X-Forwarded-For": "203.0.113.1"}).json()["address"] == "198.51.100.7"
    assert far.get("/thing", headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 200
    assert far.get("/thing", headers={"X-Forwarded-For": "203.0.113.3"}).status_code == 429
    # Rubbish in the header from a trusted proxy falls back to the connection.
    assert near.get("/thing", headers={"X-Forwarded-For": "not-an-address"}).json()["address"] == "10.0.1.5"


def test_made_up_tokens_still_count_against_their_address(monkeypatch):
    app = _app(monkeypatch, RATE_LIMIT_PER_MINUTE="100", RATE_LIMIT_PER_ADDRESS_PER_MINUTE="3")
    far = TestClient(app, client=("198.51.100.7", 5000))
    codes = [far.get("/thing", headers={"Authorization": f"Bearer made-up-token-number-{i:04d}"}).status_code for i in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_signing_in_has_a_tighter_limit_per_address(monkeypatch):
    app = _app(monkeypatch, RATE_LIMIT_ANONYMOUS_PER_MINUTE="100", RATE_LIMIT_SIGN_IN_PER_MINUTE="2")
    far = TestClient(app, client=("198.51.100.7", 5000))
    assert [far.post("/identity/login").status_code for _ in range(3)] == [200, 200, 429]
    # Another address isn't held up by the first one's tries.
    assert TestClient(app, client=("198.51.100.8", 5000)).post("/identity/login").status_code == 200
    # Reading pages isn't the sign-in limit's business.
    assert far.get("/thing").status_code == 200


def test_calls_between_modules_are_not_counted(monkeypatch):
    app = _app(monkeypatch, RATE_LIMIT_ANONYMOUS_PER_MINUTE="1")
    # What modules/inprocess.py sets on a call from another module; outside requests never carry it (modules/dispatch.py).
    marked = TestClient(app, client=("10.0.1.5", 5000))
    original = app.build_middleware_stack

    def stack():
        inner = original()

        async def mark(scope, receive, send):
            scope["bishnoi.internal"] = "crm"
            await inner(scope, receive, send)

        return mark

    app.build_middleware_stack = stack
    assert all(marked.get("/thing").status_code == 200 for _ in range(4))
