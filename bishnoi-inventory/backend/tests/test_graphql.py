"""GraphQL for reading (app/graphql_api.py): one request per page, only the
fields and reference lists asked for, and exactly the REST routes' answers,
permissions and limits, since it calls the same route functions."""

from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.conftest import receive


def gql(api, query: str, **variables):
    r = api.c.post("/graphql", json={"query": query, "variables": variables}, headers=api.h)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_form_reads_in_one_request_with_only_the_lists_it_picks_from(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 40}])
    got = gql(ana, "{ me reference { warehouses { id code locations { code } } suppliers { name } } availability }")
    assert "errors" not in got, got
    data = got["data"]
    assert set(data["reference"]) == {"warehouses", "suppliers"}  # no products, no categories
    rest = ana.get("/inventory/reference")
    assert [w["id"] for w in data["reference"]["warehouses"]] == [w["id"] for w in rest["warehouses"]]
    assert [s["name"] for s in data["reference"]["suppliers"]] == [s["name"] for s in rest["suppliers"]]
    # What's free, as the stock overview counts it.
    overview = ana.get("/inventory/stock")
    assert data["availability"] == {f"{r['product']['id']}:{r['warehouse']['id']}": r["available"] for r in overview["items"]}
    assert data["availability"][f"{world['gloves']}:{world['mnl']}"] == 40
    assert data["me"]["user"]["email"] == "ana@example.com"


def test_answers_are_the_rest_routes_own(ana, world):
    got = gql(ana, "query($id: String!) { products(q: \"glv\") product(id: $id) stock(warehouse: null) warehouses }", id=world["pcm"])
    assert "errors" not in got, got
    assert got["data"]["products"] == ana.get("/inventory/products", q="glv")
    assert got["data"]["product"] == ana.get(f"/inventory/products/{world['pcm']}")
    assert got["data"]["warehouses"] == ana.get("/inventory/warehouses")


def test_permissions_are_the_rest_routes_own(client, people, world):
    from tests.conftest import Api

    sal = Api(client, people["sal"])
    refused = client.get("/inventory/purchase-orders", headers=sal.h).status_code
    got = gql(sal, "{ purchaseOrders orders }")
    # One field refused doesn't take the page down: the rest still comes.
    if refused == 403:
        assert got["data"]["purchaseOrders"] is None and got["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert got["data"]["orders"] == sal.get("/inventory/orders")
    missing = gql(sal, '{ order(id: "nope") }')
    assert missing["data"]["order"] is None and missing["errors"][0]["extensions"]["status"] == 404


def test_arguments_are_held_to_the_routes_limits(client, ana):
    bad = gql(ana, "{ movements(limit: 9999) }")
    assert bad["data"]["movements"] is None and bad["errors"][0]["extensions"]["code"] == "BAD_INPUT"
    assert gql(ana, '{ serials(q: "") }')["errors"][0]["extensions"]["code"] == "BAD_INPUT"
    assert "errors" not in gql(ana, '{ movements(from: "2026-01-01", to: "2026-12-31", limit: 5) }')
    too_many = "{ " + " ".join(f"a{i}: unset" for i in range(20)) + " }"
    assert "errors" in gql(ana, too_many)  # aliases are limited
    assert client.post("/graphql", json={"query": "{ me }"}).status_code == 401  # signed in, as every read


def test_one_request_costs_fewer_database_queries_than_a_call_per_piece(ana, world):
    count = {"n": 0}

    def tick(*_a, **_k):
        count["n"] += 1

    event.listen(Engine, "before_cursor_execute", tick)
    try:
        for path in ("/auth/me", "/inventory/alerts", "/inventory/unset", f"/inventory/products/{world['gloves']}", "/inventory/reference"):
            ana.get(path)
        rest = count["n"]
        count["n"] = 0
        gql(ana, "query($id: String!) { me alerts unset product(id: $id) reference { suppliers { id name } } }", id=world["gloves"])
        one = count["n"]
    finally:
        event.remove(Engine, "before_cursor_execute", tick)
    assert one < rest, (one, rest)
