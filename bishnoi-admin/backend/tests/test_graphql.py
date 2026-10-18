"""GraphQL for reading (app/graphql_api.py): one request per page, and exactly
the REST routes' answers, permissions and limits, since it calls the same
route functions."""

from datetime import date, timedelta

from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.test_rbac import app, client, sign_in  # noqa: F401 (fixtures)


def gql(client, headers, query: str, **variables):
    r = client.post("/graphql", json={"query": query, "variables": variables}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def a_vehicle(client, headers) -> dict:
    due = (date.today() + timedelta(days=10)).isoformat()
    r = client.post("/admin/vehicles", json={"name": "Ford Ranger AT", "plate": "NFY 4260", "registrationDue": due}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_page_and_its_frame_read_as_the_rest_routes_answer(client):
    admin = sign_in(client)
    car = a_vehicle(client, sign_in(client, "asst@example.com"))
    got = gql(client, admin, 'query($id: String!) { me unset records(path: "vehicles") record(path: "vehicles", id: $id) permits }', id=car["id"])
    assert "errors" not in got, got
    data = got["data"]
    assert data["me"]["user"]["email"] == "admin@example.com"
    assert data["unset"] == client.get("/admin/unset", headers=admin).json()
    assert data["records"] == client.get("/admin/vehicles", headers=admin).json()
    assert data["record"] == client.get(f"/admin/vehicles/{car['id']}", headers=admin).json()
    assert data["permits"] == client.get("/admin/permits", headers=admin).json()


def test_permissions_and_limits_are_the_rest_routes_own(client):
    asst = sign_in(client, "asst@example.com")
    refused = client.get("/admin/users", headers=asst).status_code
    got = gql(client, asst, "{ users permits }")
    assert refused == 403
    # One field refused doesn't take the page down: the rest still comes.
    assert got["data"]["users"] is None and got["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert got["data"]["permits"] == client.get("/admin/permits", headers=asst).json()
    missing = gql(client, asst, '{ record(path: "vehicles", id: "nope") nothing: records(path: "spaceships") }')
    assert {e["path"][0]: e["extensions"]["status"] for e in missing["errors"]} == {"record": 404, "nothing": 404}
    assert gql(client, sign_in(client), "{ audit(limit: 999) }")["errors"][0]["extensions"]["code"] == "BAD_INPUT"
    assert client.post("/graphql", json={"query": "{ me }"}).status_code == 401  # signed in, as every read


def test_one_request_costs_fewer_database_queries_than_a_call_per_piece(client):
    admin = sign_in(client)
    count = {"n": 0}

    def tick(*_a, **_k):
        count["n"] += 1

    event.listen(Engine, "before_cursor_execute", tick)
    try:
        for path in ("/auth/me", "/admin/unset", "/admin/vehicles"):
            client.get(path, headers=admin)
        rest = count["n"]
        count["n"] = 0
        gql(client, admin, '{ me unset records(path: "vehicles") }')
        one = count["n"]
    finally:
        event.remove(Engine, "before_cursor_execute", tick)
    assert one < rest, (one, rest)
