"""Saved views (benchmark E2): a list's filters, search and sort kept by name,
one person's own or shared with everyone who sees the list."""

from tests.test_customers import crew  # noqa: F401 (a fixture)


def save(client, who, **body):
    return client.post("/views", json={"list": "companies", "name": "Overdue drugstores", "query": "status=drugstore&owner=me&page=3", **body}, headers=who)


def test_a_view_keeps_the_lists_filters_without_the_page(client, crew):  # noqa: F811
    r = save(client, crew["ria"])
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["query"] == "owner=me&status=drugstore" and v["mine"] and not v["shared"] and v["canEdit"]
    assert save(client, crew["ria"]).status_code == 409  # one name once
    got = client.get("/views?list=companies", headers=crew["ria"]).json()
    assert [x["name"] for x in got["items"]] == ["Overdue drugstores"] and got["canShare"] is False  # a salesperson keeps them to herself
    assert client.get("/views?list=companies", headers=crew["rex"]).json()["items"] == []  # private


def test_a_salesperson_keeps_views_a_lead_shares_them(client, crew):  # noqa: F811
    assert save(client, crew["ria"], shared=True).status_code == 403
    shared = save(client, crew["lia"], name="Team pipeline", shared=True).json()
    assert shared["shared"] is True
    seen = client.get("/views?list=companies", headers=crew["ria"]).json()["items"]
    assert [(x["name"], x["mine"], x["canEdit"]) for x in seen] == [("Team pipeline", False, False)]
    # Only its owner changes or deletes it.
    assert client.patch(f"/views/{shared['id']}", json={"name": "Mine now"}, headers=crew["ria"]).status_code == 403
    assert client.delete(f"/views/{shared['id']}", headers=crew["ria"]).status_code == 403
    renamed = client.patch(f"/views/{shared['id']}", json={"name": "North pipeline", "query": "?status=customer"}, headers=crew["lia"]).json()
    assert (renamed["name"], renamed["query"]) == ("North pipeline", "status=customer")
    assert client.delete(f"/views/{shared['id']}", headers=crew["lia"]).status_code == 204
    assert client.get("/views?list=companies", headers=crew["ria"]).json()["items"] == []


def test_a_view_is_for_a_list_the_person_sees(client, crew):  # noqa: F811
    assert client.post("/views", json={"list": "nothing", "name": "x"}, headers=crew["ria"]).status_code == 422
    assert client.get("/views?list=deals", headers=crew["ria"]).status_code == 200
