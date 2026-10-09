"""A division's customers shown to other divisions, or kept to itself
(app/routers/sharing.py): set by the administrator, or the division's manager."""

from app.models import Team, User
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)


def names(client, headers, name):
    r = client.get("/companies/lookalikes", params={"name": name}, headers=headers)
    assert r.status_code == 200, r.text
    return [(c["name"], c["teamName"]) for c in r.json()]


def test_a_division_can_keep_its_customers_to_itself(app, client, ana, crew):
    company(client, crew["ria"], "St. Lukes Clinic")  # North's
    # Shown, as before: South is told it exists, by name and division only.
    assert names(client, crew["sam"], "St. Lukes Clinic") == [("St. Lukes Clinic", "North")]

    north = next(t for t in client.get("/customer-sharing", headers=ana).json() if t["name"] == "North")
    assert north["shareCustomers"] is True
    r = client.put(f"/customer-sharing/{north['id']}", json={"shareCustomers": False}, headers=ana)
    assert r.status_code == 200 and r.json()["shareCustomers"] is False

    assert names(client, crew["sam"], "St. Lukes Clinic") == []  # South no longer sees it
    assert names(client, crew["rex"], "St. Lukes Clinic") == [("St. Lukes Clinic", "North")]  # North still does


def test_only_the_administrator_or_the_divisions_manager_sets_it(app, client, crew):
    with app.state.sessions() as db:
        north = db.query(Team).filter_by(name="North").one()
        north_id = north.id
    # A team lead and a salesperson: nothing to set, and refused if they try.
    assert client.get("/customer-sharing", headers=crew["lia"]).json() == []
    assert client.put(f"/customer-sharing/{north_id}", json={"shareCustomers": False}, headers=crew["ria"]).status_code == 404
    # North's manager may.
    with app.state.sessions() as db:
        lia = db.query(User).filter_by(email="lia@example.com").one()
        db.get(Team, north_id).manager_id = lia.id
        db.commit()
    assert [t["name"] for t in client.get("/customer-sharing", headers=crew["lia"]).json()] == ["North"]
    assert client.put(f"/customer-sharing/{north_id}", json={"shareCustomers": False}, headers=crew["lia"]).status_code == 200
