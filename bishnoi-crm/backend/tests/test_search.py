"""One search across the CRM for the command menu (benchmark G2): a few of
each kind, only what the person may see and reach."""

from tests.test_customers import company, contact, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids  # noqa: F401 (fixtures)


def groups(client, who, q) -> dict[str, list[str]]:
    r = client.get(f"/search?q={q}", headers=who)
    assert r.status_code == 200, r.text
    return {g["kind"]: [i["title"] for i in g["items"]] for g in r.json()["groups"]}


def test_search_finds_each_kind_the_person_reaches(client, crew, ids):  # noqa: F811
    mercury = company(client, crew["ria"], "Mercury Drug Pasig", city="Pasig")
    company(client, crew["sam"], "Mercury Drug Cebu")  # another team's
    contact(client, crew["ria"], "Maria", lastName="Mercado", companyId=mercury["id"])
    got = groups(client, crew["ria"], "merc")
    assert got["customers"] == ["Mercury Drug Pasig"]  # Sam's isn't hers to reach
    assert got["contacts"] == ["Maria Mercado"]
    assert "Mercury Drug Cebu" in groups(client, crew["max"], "mercury")["customers"]  # a role over every team
    assert groups(client, crew["ria"], "amox")["products"][0].startswith("Amox")  # the catalogue, by name or code


def test_names_starting_with_the_search_come_first(client, crew):  # noqa: F811
    company(client, crew["ria"], "Big Mercury Store")
    company(client, crew["ria"], "Mercury Express")
    assert groups(client, crew["ria"], "mercury")["customers"] == ["Mercury Express", "Big Mercury Store"]
    # How many match in all (the menu's scope tabs), past what one page shows, and the preview's facts and steps.
    first = client.get("/search?q=mercury&limit=1", headers=crew["ria"]).json()["groups"][0]
    assert first["total"] == 2 and len(first["items"]) == 1
    assert first["items"][0]["facts"][-1]["label"] == "Assigned to"
    assert first["items"][0]["actions"][0] == {"label": "Open customer", "href": first["items"][0]["href"]}
    assert client.get("/search?q=", headers=crew["ria"]).status_code == 422
