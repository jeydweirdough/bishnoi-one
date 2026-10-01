"""The structured visit record (P6): products detailed with their message and
the doctor's reaction, and the next visit's objective."""

import pytest

from app.tools.users import make_demo_catalogue
from tests.test_field import MONTH, doctor, field, visit  # noqa: F401  (field is a fixture)


@pytest.fixture
def products(app, client, field) -> dict[str, str]:  # noqa: F811
    with app.state.sessions() as db:
        make_demo_catalogue(db)
    items = client.get("/products", headers=field["ana"]).json()["items"]
    return {p["code"]: p["id"] for p in items}


def test_a_visit_records_what_was_detailed_and_how_it_landed(client, field, products):
    doc = doctor(client, field, "Dr. Cruz", "fay")
    v = visit(
        client,
        field["fay"],
        doc,
        detailing=[
            {"productId": products["AMX-500"], "message": "Twice-daily dosing", "reaction": "will_prescribe"},
            {"productId": products["CTZ-10"], "reaction": "concerns"},
        ],
        nextObjective="Bring the dosing study",
    )
    assert [(d["productName"], d["message"], d["reaction"]) for d in v["detailing"]][1][1:] == (None, "concerns")
    assert v["detailing"][0]["message"] == "Twice-daily dosing" and v["nextObjective"] == "Bring the dosing study"

    # The next visit's form shows what this one set out to do, and the products (names only).
    brief = client.get(f"/field/visit-brief?company={doc['id']}", headers=field["fay"]).json()
    assert brief["lastObjective"]["text"] == "Bring the dosing study" and brief["lastObjective"]["by"]["name"] == "Fay"
    assert {"id", "name", "strength"} == set(brief["products"][0]) and brief["reactions"][0] == "will_prescribe"


def test_detailing_is_checked(client, field, products):
    doc = doctor(client, field, "Dr. Cruz", "fay")
    base = {"companyId": doc["id"], "outcome": "other", "visitedAt": f"{MONTH}-10T10:00:00", "location": {"latitude": 14.5, "longitude": 121.0, "accuracyM": 10}}
    twice = [{"productId": products["AMX-500"], "reaction": "neutral"}] * 2
    r = client.post("/visits", json={**base, "detailing": twice}, headers=field["fay"])
    assert r.status_code == 422 and "twice" in r.text
    r = client.post("/visits", json={**base, "detailing": [{"productId": "nope", "reaction": "neutral"}]}, headers=field["fay"])
    assert r.status_code == 422
    r = client.post("/visits", json={**base, "detailing": [{"productId": products["AMX-500"], "reaction": "loved it"}]}, headers=field["fay"])
    assert r.status_code == 422
    # An agent can't ask about another agent's doctor.
    sols = doctor(client, field, "Dr. Reyes", "sol")
    assert client.get(f"/field/visit-brief?company={sols['id']}", headers=field["fay"]).status_code == 404


def test_the_month_summary_counts_products_detailed_and_reactions(client, field, products):
    a, b = doctor(client, field, "Dr. Cruz", "fay"), doctor(client, field, "Dr. Lim", "finn")
    visit(client, field["fay"], a, detailing=[{"productId": products["AMX-500"], "reaction": "will_prescribe"}])
    visit(client, field["finn"], b, detailing=[{"productId": products["AMX-500"], "reaction": "concerns"}, {"productId": products["CTZ-10"], "reaction": "interested"}])
    visit(client, field["finn"], b)
    summary = client.get(f"/field/detailing?month={MONTH}", headers=field["lia"]).json()
    assert (summary["visits"], summary["detailedVisits"]) == (3, 2)
    amox = summary["products"][0]
    assert (amox["visits"], amox["doctors"], amox["reactions"]["will_prescribe"], amox["reactions"]["concerns"]) == (2, 2, 1, 1)
    # Fay sees only her own.
    assert client.get(f"/field/detailing?month={MONTH}", headers=field["fay"]).json()["detailedVisits"] == 1
