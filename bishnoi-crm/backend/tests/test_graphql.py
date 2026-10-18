"""GraphQL for reading (app/graphql_api.py): one request per page, only the
fields asked for, and exactly the REST routes' answers, permissions, reach
and limits, since it calls the same route functions."""

from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.test_customers import company, contact, crew  # noqa: F401 (crew is a fixture)


def gql(client, headers, query: str, **variables):
    r = client.post("/graphql", json={"query": query, "variables": variables}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_page_reads_in_one_request_with_only_the_fields_it_asks_for(client, ana):
    acme = company(client, ana, "Acme Hospital", city="Makati")
    contact(client, ana, "Maria", companyId=acme["id"], email="maria@acme.test")
    got = gql(
        client,
        ana,
        """query Customer($id: String!) {
             me
             company(id: $id) { name code city owner { name } contacts { name email } }
             customerTypes { code name }
             people { id name isMe }
           }""",
        id=acme["id"],
    )
    assert "errors" not in got, got
    data = got["data"]
    assert data["company"] == {"name": "Acme Hospital", "code": acme["code"], "city": "Makati", "owner": {"name": acme["owner"]["name"]}, "contacts": [{"name": "Maria", "email": "maria@acme.test"}]}
    assert data["me"]["user"]["email"] == "ana@example.com"
    # Exactly REST's answers, trimmed to what was asked.
    assert [t["code"] for t in data["customerTypes"]] == [t["code"] for t in client.get("/customer-types", headers=ana).json()]
    assert [p["id"] for p in data["people"]] == [p["id"] for p in client.get("/people/assignable", headers=ana).json()]


def test_permissions_and_reach_are_the_rest_routes_own(client, ana, crew):
    theirs = company(client, ana, "Ana's customer")
    company(client, crew["ria"], "Ria's customer")
    rep = crew["ria"]  # a salesperson: their own customers only, no reports
    got = gql(client, rep, "{ companies(limit: 50) { total items { name } } peopleInsights }")
    assert [c["name"] for c in got["data"]["companies"]["items"]] == [c["name"] for c in client.get("/companies?limit=50", headers=rep).json()["items"]]
    assert "Ana's customer" not in [c["name"] for c in got["data"]["companies"]["items"]]
    # One field refused doesn't take the page down: the rest still comes.
    assert got["data"]["peopleInsights"] is None
    assert got["errors"][0]["path"] == ["peopleInsights"] and got["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    # Out of reach reads as not found, as in REST.
    missing = gql(client, rep, "query($id: String!) { company(id: $id) { name } }", id=theirs["id"])
    assert missing["data"]["company"] is None and missing["errors"][0]["extensions"]["status"] == 404


def test_arguments_are_held_to_the_routes_limits_and_queries_to_ours(client, ana):
    bad = gql(client, ana, "{ salesTrend(months: 99) }")
    assert bad["data"]["salesTrend"] is None and bad["errors"][0]["extensions"]["code"] == "BAD_INPUT"
    deep = "{ companies { items { owner { name } } } }".replace("owner { name }", "owner { name }")
    assert "errors" not in gql(client, ana, deep)
    too_many = "{ " + " ".join(f"a{i}: me" for i in range(20)) + " }"
    assert "errors" in gql(client, ana, too_many)  # aliases are limited
    assert client.post("/graphql", json={"query": "{ me }"}).status_code == 401  # signed in, as every read


def test_one_request_costs_fewer_database_queries_than_a_call_per_piece(client, ana):
    acme = company(client, ana, "Acme Hospital")
    count = {"n": 0}

    def tick(*_a, **_k):
        count["n"] += 1

    event.listen(Engine, "before_cursor_execute", tick)
    try:
        for path in (f"/companies/{acme['id']}", "/customer-types", "/people/assignable"):
            client.get(path, headers=ana)
        rest = count["n"]
        count["n"] = 0
        gql(client, ana, "query($id: String!) { company(id: $id) { name } customerTypes { code } people { id } }", id=acme["id"])
        one = count["n"]
    finally:
        event.remove(Engine, "before_cursor_execute", tick)
    assert one < rest, (one, rest)


def test_performance_reads_as_the_scorecard(client, ana, crew):
    rep = crew["ria"]
    got = gql(client, rep, '{ performance(view: "mine") before: performance(view: "mine", month: "2026-01") }')
    assert "errors" not in got, got
    assert got["data"]["performance"] == client.get("/kpi-scorecard?view=mine", headers=rep).json()
    assert got["data"]["before"]["month"] == "2026-01"


def test_a_field_agents_home_in_one_request(client, ana):
    # The field Home's query: the list by the plan, and the month's coverage of it.
    data = gql(client, ana, '{ doctors: fieldDoctors(limit: 5, sort: "plan") coverage: fieldCoverage }')["data"]
    assert {"items", "total"} <= set(data["doctors"]) and data["coverage"]["goalPct"] == 80
