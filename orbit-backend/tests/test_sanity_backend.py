"""The Sanity backend's requests, checked against a fake server, so the wire
format is right before a real project is connected."""

import json

import httpx
import pytest

from app.scope import Scope
from app.store.query import Eq, Query
from app.store.records import ConflictError, Create, Delete, Patch, StoreError
from app.store.sanity import SanityBackend

BNB_MD = Scope("bnb", "md-telesales")


def backend(handler) -> tuple[SanityBackend, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(record))
    return SanityBackend("abc123", "production", "secret-token", "v2025-02-19", client), seen


def test_query_is_posted_with_params_and_token():
    sanity, seen = backend(lambda r: httpx.Response(200, json={"result": [{"_id": "x"}]}))
    assert sanity.fetch(Query("customer", {BNB_MD}, (Eq("status", "lead"),))) == [{"_id": "x"}]

    request = seen[0]
    assert request.method == "POST"
    assert str(request.url).startswith("https://abc123.api.sanity.io/v2025-02-19/data/query/production")
    assert request.url.params["perspective"] == "published"
    assert request.headers["Authorization"] == "Bearer secret-token"
    body = json.loads(request.content)
    assert body["query"].startswith("*[_type == $type && scopeKey in $scopeKeys && status == $p0]")
    assert body["params"] == {"type": "customer", "scopeKeys": ["bnb/md-telesales"], "p0": "lead"}


def test_count():
    sanity, seen = backend(lambda r: httpx.Response(200, json={"result": 7}))
    assert sanity.count(Query("customer", {BNB_MD})) == 7
    assert json.loads(seen[0].content)["query"].startswith("count(*[")


def test_mutations_are_one_transaction():
    sanity, seen = backend(lambda r: httpx.Response(200, json={"transactionId": "t1", "results": []}))
    doc = {"_id": "c1", "_type": "customer", "name": "Dr. A", **BNB_MD.stamp()}
    sanity.commit([Create(doc), Patch("c1", {"name": "Dr. B"}, ("phone",), if_revision="r1"), Delete("a1")])

    request = seen[0]
    assert str(request.url).startswith("https://abc123.api.sanity.io/v2025-02-19/data/mutate/production")
    assert request.url.params["visibility"] == "sync"
    assert json.loads(request.content) == {
        "mutations": [
            {"create": doc},
            {"patch": {"id": "c1", "set": {"name": "Dr. B"}, "unset": ["phone"], "ifRevisionID": "r1"}},
            {"delete": {"id": "a1"}},
        ]
    }


def test_errors_are_mapped():
    sanity, _ = backend(lambda r: httpx.Response(409, json={"error": {"description": "revision mismatch"}}))
    with pytest.raises(ConflictError):
        sanity.commit([Delete("x")])

    sanity, _ = backend(lambda r: httpx.Response(401, json={"error": "Unauthorized"}))
    with pytest.raises(StoreError):
        sanity.fetch(Query("customer", {BNB_MD}))

    def down(request):
        raise httpx.ConnectError("no route")

    sanity, _ = backend(down)
    with pytest.raises(StoreError):
        sanity.fetch(Query("customer", {BNB_MD}))
