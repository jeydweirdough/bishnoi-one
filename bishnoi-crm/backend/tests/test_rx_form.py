"""The Rx team's own customer form (app/tools/rx_form.py): its fields and types
are on Rx customers only, a customer code is unique, and other teams keep
their form. Also the look-alikes shown while a new customer is typed in."""

import pytest
from sqlalchemy import select

from app.models import FormField, Role, Team, User
from app.security import hash_password
from app.tools.rx_form import set_up
from tests.conftest import PASSWORD, bearer, role_id, sign_in
from tests.test_quotes import errors


@pytest.fixture
def rx(app, client) -> dict[str, dict]:
    """Teams STC and URO (Rx) and B2C. Sol sells in STC, Ugo in URO, Bea in B2C.
    The Rx form is set up. Returns sign-in headers, and each team's id under "teams"."""
    with app.state.sessions() as db:
        teams = {n: Team(name=n) for n in ("STC", "URO", "B2C")}
        db.add_all(teams.values())
        db.flush()
        for name, team in (("sol", "STC"), ("ugo", "URO"), ("bea", "B2C")):
            db.add(User(email=f"{name}@example.com", full_name=name.title(), password_hash=hash_password(PASSWORD), role_id=role_id(db, "Salesperson"), team_id=teams[team].id))
        db.commit()
        set_up(db)
        ids = {n: t.id for n, t in teams.items()}
    return {**{n: bearer(sign_in(client, f"{n}@example.com")) for n in ("sol", "ugo", "bea")}, "teams": ids}


def new(client, headers, **body):
    return client.post("/companies", json={"name": "Dr. Santos", **body}, headers=headers)


def test_an_rx_customer_has_the_rx_fields_and_types(client, rx):
    r = new(client, rx["sol"], status="fellow", extra={"x_department": "MED ONCO", "x_region": "NCR", "x_category": "A", "x_birth_date": "1980-05-02"})
    assert r.status_code == 201, r.text
    assert r.json()["extra"]["x_department"] == "MED ONCO" and r.json()["status"] == "fellow"
    # The general types aren't the Rx team's.
    r = new(client, rx["sol"], name="Clinic", status="prospect")
    assert r.status_code == 422 and errors(r) == {"status": "Pick a type from the list."}
    # Nobody says: the first type on the Rx list.
    assert new(client, rx["ugo"], name="Dr. Lim").json()["status"] == "doctor"


def test_other_teams_keep_their_form(client, rx):
    r = new(client, rx["bea"], extra={"x_department": "HEMA"})
    assert r.status_code == 422 and "x_department" in str(r.json())
    assert new(client, rx["bea"], name="Juan", status="fellow").status_code == 422
    assert new(client, rx["bea"], name="Juan", status="patient").json()["status"] == "patient"  # B2C's own
    assert new(client, rx["bea"], name="Clinic", status="prospect").status_code == 201


def test_the_system_gives_each_customer_its_code(client, rx):
    first = new(client, rx["sol"]).json()
    second = new(client, rx["bea"], name="Juan").json()
    assert (first["code"], second["code"]) == ("CRM-000001", "CRM-000002")
    # Nobody sets or changes it.
    assert new(client, rx["sol"], name="Dr. X", code="CRM-999999").status_code == 422
    assert client.patch(f"/companies/{first['id']}", json={"code": "CRM-000777"}, headers=rx["sol"]).status_code == 422
    # It finds the customer.
    assert [c["code"] for c in client.get("/companies?q=crm-000001", headers=rx["sol"]).json()["items"]] == ["CRM-000001"]
    # The numbers keep counting, across every team.
    assert new(client, rx["ugo"], name="Dr. Lim").json()["code"] == "CRM-000003"


def test_the_form_says_whose_each_field_is(client, rx, ana):
    form = client.get("/forms/company", headers=rx["sol"]).json()
    by_key = {f["key"]: f for s in form["sections"] for f in s["fields"]}
    dept, industry = by_key["x_department"], by_key["industry"]
    assert set(dept["onlyTeams"]) == {rx["teams"]["STC"], rx["teams"]["URO"]} and dept["optionNames"]["MED ONCO"] == "Medical oncology"
    assert set(industry["exceptTeams"]) == {rx["teams"]["STC"], rx["teams"]["URO"]}
    assert by_key["ownerId"]["label"] == "Assigned to" and "x_customer_code" not in by_key
    # Saving the form in Settings keeps all of it.
    everything = client.get("/forms/company?all=true", headers=ana).json()
    body = {"sections": [{**s, "fields": [{k: v for k, v in f.items() if k not in ("used", "key", "standard", "locked", "sharedList", "picks")} for f in s["fields"]]} for s in everything["sections"]]}
    again = client.put("/admin/forms/company", json=body, headers=ana)
    assert again.status_code == 200, again.text
    kept = {f["key"]: f for s in again.json()["sections"] for f in s["fields"]}
    assert kept["x_department"]["onlyTeams"] == dept["onlyTeams"] and kept["x_region"]["optionNames"]["NCR"] == "National Capital Region"


def test_setting_up_twice_changes_nothing(app, rx):
    with app.state.sessions() as db:
        before = db.scalar(select(FormField.id).where(FormField.key == "x_department"))
        set_up(db)
        assert db.scalars(select(FormField).where(FormField.key == "x_department")).all()[0].id == before
        assert len(db.scalars(select(FormField).where(FormField.key == "x_department")).all()) == 1


def test_look_alikes_while_typing(client, rx):
    new(client, rx["sol"], name="Dr. Maria Santos", phone="0917 555 0101")
    new(client, rx["bea"], name="Dr. Maria Reyes")
    mine = client.get("/companies/lookalikes?name=maria", headers=rx["sol"]).json()
    assert [c["name"] for c in mine] == ["Dr. Maria Santos"]  # part of a name: only those in reach
    assert mine[0]["canOpen"] and mine[0]["owner"] == "Sol"
    theirs = client.get("/companies/lookalikes?name=Dr. Maria Reyes", headers=rx["sol"]).json()
    assert [(c["name"], c["canOpen"], c["owner"]) for c in theirs] == [("Dr. Maria Reyes", False, None)]  # the whole name: anyone's
    by_phone = client.get("/companies/lookalikes?phone=%2B63 917 555 0101", headers=rx["bea"]).json()
    assert [c["name"] for c in by_phone] == ["Dr. Maria Santos"]


def test_what_a_customer_is_asked_follows_its_type(app, client, rx):
    with app.state.sessions() as db:
        from app.models import Product

        db.add_all([Product(code="ONC-1", name="Onco One", generic_name="Imatinib"), Product(code="ANE-1", name="Sleepwell", generic_name="Propofol")])
        db.commit()
    # A doctor is profiled: products of interest from the catalogue, and molecules.
    r = new(client, rx["sol"], status="doctor", extra={"x_patients_per_day": 30, "x_product_interest": ["ONC-1"], "x_molecule_1": "Imatinib", "x_molecule_1_patients": 12})
    assert r.status_code == 201, r.text
    assert r.json()["extra"]["x_product_interest"] == ["ONC-1"]
    assert new(client, rx["sol"], name="Dr. B", status="doctor", extra={"x_product_interest": ["NOPE"]}).status_code == 422
    # A hospital isn't asked a doctor's profile, nor a person's birthday.
    for field, value in (("x_patients_per_day", 5), ("x_birth_date", "1980-01-01"), ("x_department", "HEMA")):
        r = new(client, rx["sol"], name="Big Hospital", status="hospital", extra={field: value})
        assert r.status_code == 422 and field in str(r.json()), field
    assert new(client, rx["sol"], name="Big Hospital", status="hospital", extra={"x_category": "A", "x_region": "NCR"}).status_code == 201
    # A pharmacist is a person, but not a doctor.
    assert new(client, rx["sol"], name="Ph. Cruz", status="pharmacist", extra={"x_birth_date": "1990-02-02"}).status_code == 201
    assert new(client, rx["sol"], name="Ph. Lim", status="pharmacist", extra={"x_patients_per_day": 3}).status_code == 422
    # The form says whom each field is for, and what a products field offers.
    by_key = {f["key"]: f for s in client.get("/forms/company", headers=rx["sol"]).json()["sections"] for f in s["fields"]}
    assert by_key["x_patients_per_day"]["onlyTypes"] == ["doctor", "fellow", "resident"]
    assert {p["value"] for p in by_key["x_product_interest"]["picks"]} >= {"ONC-1", "ANE-1"}
    assert "Imatinib" in {p["value"] for p in by_key["x_molecule_1"]["picks"]}


def test_a_products_field_can_leave_products_out(app, client, rx, ana):
    with app.state.sessions() as db:
        from app.models import Product

        db.add(Product(code="ANE-1", name="Sleepwell", generic_name="Propofol"))
        db.commit()
    everything = client.get("/forms/company?all=true", headers=ana).json()
    drop = ("used", "key", "standard", "locked", "sharedList", "picks")
    sections = [
        {**s, "fields": [{k: v for k, v in f.items() if k not in drop} | ({"options": ["ANE-1"]} if f["key"] == "x_product_interest" else {}) for f in s["fields"]]}
        for s in everything["sections"]
    ]
    assert client.put("/admin/forms/company", json={"sections": sections}, headers=ana).status_code == 200
    r = new(client, rx["sol"], status="doctor", extra={"x_product_interest": ["ANE-1"]})
    assert r.status_code == 422  # left out of this field: anaesthesia isn't promoted
