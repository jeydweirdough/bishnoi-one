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


def test_employee_ids_are_given_and_never_shared(client, ana, crew):
    # Everyone has one, and no two people the same.
    people = client.get("/admin/users", headers=ana).json()
    codes = [u["employeeId"] for u in people]
    assert all(codes) and len(set(codes)) == len(codes)
    # Someone added gets the next free number, without anyone typing it.
    highest = max(int(c.split("-")[1]) for c in codes if c.startswith("EMP-"))
    role = next(r for r in client.get("/admin/roles", headers=ana).json()["roles"] if r["name"] == "Salesperson")
    new = client.post("/admin/users", json={"email": "new@example.com", "fullName": "New Person", "roleId": role["id"], "password": "a long password 1"}, headers=ana).json()
    assert new["employeeId"] == f"EMP-{highest + 1:04d}"
    # Nobody can type one, on adding or on changing someone.
    r = client.post("/admin/users", json={"email": "other@example.com", "fullName": "Other", "roleId": role["id"], "password": "a long password 1", "employeeId": "EMP-9999"}, headers=ana)
    assert r.status_code == 422
    rex = next(u for u in people if u["email"] == "rex@example.com")
    r = client.patch(f"/admin/users/{rex['id']}", json={"employeeId": new["employeeId"]}, headers=ana)
    assert r.status_code == 422
    assert client.get(f"/admin/users/{rex['id']}", headers=ana).json()["employeeId"] == rex["employeeId"]
