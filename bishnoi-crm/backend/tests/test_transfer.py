"""Handing a customer to someone else: by their employee ID, typed, with the
contacts and open deals the previous owner was working on there."""

from sqlalchemy import select

from app.models import User
from tests.test_customers import company, contact, crew  # noqa: F401 (crew is a fixture)
from tests.test_deals import deal
from tests.test_quotes import errors


def give_ids(app, **codes) -> None:
    with app.state.sessions() as db:
        for email, code in codes.items():
            db.scalar(select(User).where(User.email == f"{email}@example.com")).employee_id = code
        db.commit()


def test_a_customer_goes_to_the_person_with_that_employee_id(app, client, crew):
    give_ids(app, ria="EMP-1", sam="EMP-2")
    acme = company(client, crew["ria"])
    maria = contact(client, crew["ria"], companyId=acme["id"])
    open_deal = deal(client, crew["ria"], acme)
    lost = deal(client, crew["ria"], acme, name="Old order")
    client.post(f"/deals/{lost['id']}/lose", json={"reason": "Price"}, headers=crew["ria"])

    # Shown first: who it would go to. Typed loosely, found all the same.
    who = client.get(f"/companies/{acme['id']}/transfer?employeeId=emp-2 ", headers=crew["ria"]).json()
    assert (who["name"], who["employeeId"], who["role"], who["team"]["name"]) == ("Sam", "EMP-2", "Salesperson", "South")

    done = client.post(f"/companies/{acme['id']}/transfer", json={"employeeId": "EMP-2"}, headers=crew["ria"]).json()
    assert done["to"]["name"] == "Sam" and done["moved"] == {"contacts": 1, "deals": 1} and done["stillYours"] is False
    assert client.get(f"/companies/{acme['id']}", headers=crew["ria"]).status_code == 404  # Ria no longer reaches it
    seen = client.get(f"/companies/{acme['id']}", headers=crew["sam"]).json()
    assert seen["owner"]["name"] == "Sam" and [c["id"] for c in seen["contacts"]] == [maria["id"]]
    assert client.get(f"/deals/{open_deal['id']}", headers=crew["sam"]).json()["owner"]["name"] == "Sam"
    assert client.get(f"/deals/{lost['id']}", headers=crew["sam"]).status_code == 404  # closed deals stay with who closed them


def test_the_employee_id_must_name_someone_who_can_take_it(app, client, crew, ana):
    give_ids(app, ria="EMP-1", rex="EMP-3")
    acme = company(client, crew["ria"])
    url = f"/companies/{acme['id']}/transfer"
    r = client.post(url, json={"employeeId": "EMP-404"}, headers=crew["ria"])
    assert r.status_code == 422 and "Nobody here" in errors(r)["employeeId"]
    r = client.post(url, json={"employeeId": "EMP-1"}, headers=crew["ria"])
    assert r.status_code == 422 and "already" in errors(r)["employeeId"]
    with app.state.sessions() as db:
        db.scalar(select(User).where(User.email == "rex@example.com")).is_active = False
        db.commit()
    r = client.post(url, json={"employeeId": "EMP-3"}, headers=crew["ria"])
    assert r.status_code == 422 and "Nobody here" in errors(r)["employeeId"]  # switched off
    # Out of reach is not found, as everywhere.
    assert client.post(url, json={"employeeId": "EMP-1"}, headers=crew["sam"]).status_code == 404


def test_administrators_set_employee_ids_unique_and_in_capitals(client, ana, crew):
    people = {u["email"]: u for u in client.get("/admin/users", headers=ana).json()}
    ria, rex = people["ria@example.com"], people["rex@example.com"]
    set_ria = client.patch(f"/admin/users/{ria['id']}", json={"employeeId": " emp-0012 "}, headers=ana).json()
    assert set_ria["employeeId"] == "EMP-0012"
    r = client.patch(f"/admin/users/{rex['id']}", json={"employeeId": "Emp-0012"}, headers=ana)
    assert r.status_code == 422 and "already" in errors(r)["employeeId"]
    cleared = client.patch(f"/admin/users/{ria['id']}", json={"employeeId": ""}, headers=ana).json()
    assert cleared["employeeId"] is None
