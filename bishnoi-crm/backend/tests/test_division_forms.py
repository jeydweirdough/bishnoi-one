"""HOS, B2B and BID customer forms (app/tools/division_forms.py): each
division's own types and fields, and only what fits each kind of customer."""

import pytest

from app.models import Product, Team, User
from app.security import hash_password
from app.tools import division_forms, rx_form
from tests.conftest import PASSWORD, bearer, role_id, sign_in


@pytest.fixture
def team(app, client) -> dict[str, dict]:
    """Teams STC (Rx), HOS, B2B and BID, a salesperson in each (named for it),
    and the forms set up. Returns sign-in headers."""
    with app.state.sessions() as db:
        for name in ("STC", "HOS", "B2B", "BID"):
            t = Team(name=name)
            db.add(t)
            db.flush()
            db.add(User(email=f"{name.lower()}@example.com", full_name=name, password_hash=hash_password(PASSWORD), role_id=role_id(db, "Salesperson"), team_id=t.id))
        db.add(Product(code="ONC-1", name="Onco One", generic_name="Imatinib"))
        db.commit()
        rx_form.set_up(db)
        division_forms.set_up(db)
    return {n: bearer(sign_in(client, f"{n.lower()}@example.com")) for n in ("STC", "HOS", "B2B", "BID")}


def add(client, headers, **body):
    return client.post("/companies", json={"name": "Somewhere", **body}, headers=headers)


def test_hos_profiles_cancer_care(client, team):
    r = add(client, team["HOS"], status="cancer_center", extra={"x_cancer_patients": 120, "x_cancer_types": ["Breast", "Lung"], "x_formulary": ["ONC-1"], "x_region": "NCR"})
    assert r.status_code == 201, r.text
    # An oncologist is profiled as Rx profiles its doctors.
    r = add(client, team["HOS"], name="Dr. Onco", status="oncologist", extra={"x_department": "MED ONCO", "x_patients_per_day": 25, "x_molecule_1": "Imatinib"})
    assert r.status_code == 201, r.text
    # A hospital isn't asked a doctor's profile, and the general types aren't HOS's.
    assert add(client, team["HOS"], status="hospital", extra={"x_patients_per_day": 3}).status_code == 422
    assert add(client, team["HOS"], status="prospect").status_code == 422


def test_b2b_and_bid_ask_what_fits_them(client, team):
    r = add(client, team["B2B"], status="distributor", extra={"tin": "123-456-789-000", "x_credit_terms": "30 days", "x_products_carried": ["ONC-1"], "x_monthly_volume": 250000})
    assert r.status_code == 201, r.text
    assert add(client, team["B2B"], status="wholesaler", extra={"x_cancer_patients": 5}).status_code == 422  # HOS's
    r = add(client, team["BID"], status="doh_office", extra={"x_procurement_office": "BAC secretariat", "x_philgeps": "12345", "x_region": "Region IV-A"})
    assert r.status_code == 201, r.text
    assert add(client, team["BID"], status="doh_office", extra={"tin": "1"}).status_code == 422  # B2B's
    # Rx doesn't get the other divisions' types.
    assert add(client, team["STC"], status="doh_office").status_code == 422


def test_setting_up_twice_changes_nothing(app, team):
    with app.state.sessions() as db:
        assert division_forms.set_up(db)  # runs again without adding anything twice
        from sqlalchemy import func, select

        from app.models import FormField

        assert db.scalar(select(func.count()).select_from(FormField).where(FormField.key == "x_formulary")) == 1


def test_a_doctor_links_to_their_hospital(client, team):
    # A HOS hospital, and an Rx doctor who works there.
    hospital = add(client, team["HOS"], name="Manila Cancer Center", status="cancer_center").json()
    options = client.get("/companies/link-options?field=x_hospital&q=cancer", headers=team["STC"]).json()
    assert [o["name"] for o in options] == ["Manila Cancer Center"]  # any division's
    doctor = add(client, team["STC"], name="Dr. Reyes", status="doctor", extra={"x_hospital": hospital["id"]})
    assert doctor.status_code == 201, doctor.text
    seen = client.get(f"/companies/{doctor.json()['id']}", headers=team["STC"]).json()
    assert seen["links"]["x_hospital"] == {"id": hospital["id"], "name": "Manila Cancer Center", "teamName": "HOS", "canOpen": False}
    # Only a hospital-like customer can be one; and not the customer itself.
    other_doctor = doctor.json()["id"]
    assert add(client, team["STC"], name="Dr. X", status="doctor", extra={"x_hospital": other_doctor}).status_code == 422
    # From the hospital, the doctors there that one can see.
    assert client.get(f"/companies/{hospital['id']}", headers=team["HOS"]).json()["linkedHere"] == []  # Rx's doctor: not HOS's to see
    hos_doctor = add(client, team["HOS"], name="Dr. Onco", status="oncologist", extra={"x_hospital": hospital["id"]}).json()
    here = client.get(f"/companies/{hospital['id']}", headers=team["HOS"]).json()["linkedHere"]
    assert [(h["id"], h["field"]) for h in here] == [(hos_doctor["id"], "Hospital name")]
