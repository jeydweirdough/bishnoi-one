"""Each company's data in a database of its own (app/tenants.py): nothing one
company keeps is seen by another, and a session opens its own company only."""

from app.models import Role, User
from app.security import hash_password
from app.tenants import database_url, slug_of_token
from tests.conftest import PASSWORD, role_id

NORTHWIND = {"X-Bishnoi-Company": "northwind"}


def test_where_each_company_is_kept():
    assert database_url("sqlite:///.data/crm.db", "getmeds") == "sqlite:///.data/crm-getmeds.db"
    assert database_url("postgresql+psycopg://u:p@host/neondb?sslmode=require", "north-wind") == "postgresql+psycopg://u:p@host/neondb_north_wind?sslmode=require"
    assert slug_of_token("getmeds.abc") == "getmeds" and slug_of_token("abc") is None and slug_of_token("Bad!.abc") is None


def test_companies_keep_apart(app, client, ana):
    # Northwind: a database of its own, made the first time it's asked for, with its own people.
    with app.state.tenants.get("northwind").sessions() as db:
        assert db.query(User).count() == 0 and db.query(Role).count() > 0
        db.add(User(email="nia@northwind.test", full_name="Nia Santos", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Administrator")))
        db.commit()
    # Ana is GetMeds's: not an account at Northwind.
    assert client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}, headers=NORTHWIND).status_code == 401
    r = client.post("/auth/login", json={"email": "nia@northwind.test", "password": PASSWORD}, headers=NORTHWIND)
    assert r.status_code == 200 and r.json()["accessToken"].startswith("northwind.")
    nia = {"Authorization": f"Bearer {r.json()['accessToken']}"}

    made = client.post("/companies", headers=ana, json={"name": "St. Luke's Medical Center"})
    assert made.status_code in (200, 201), made.text
    names = lambda who: [c["name"] for c in client.get("/companies", headers=who).json()["items"]]
    assert "St. Luke's Medical Center" in names(ana) and names(nia) == []

    # A session is its company's: naming another company doesn't move it there.
    assert client.get("/companies", headers={**ana, **NORTHWIND}).json()["items"] == client.get("/companies", headers=ana).json()["items"]
    # And one company's token, given another company's name, isn't a session there.
    forged = {"Authorization": "Bearer northwind." + ana["Authorization"].split(".", 1)[1]}
    assert client.get("/companies", headers=forged).status_code == 401

    assert {"getmeds", "northwind"} <= set(app.state.tenants.known())


def test_the_first_administrator_is_made_in_one_company_only(tmp_path):
    from pydantic import SecretStr

    from app.config import Settings
    from app.main import create_app

    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'crm.db').as_posix()}",
                        first_admin_email="boss@example.com", first_admin_password=SecretStr(PASSWORD))
    app = create_app(settings)
    try:
        with app.state.tenants.get("getmeds").sessions() as db:
            assert [u.email for u in db.query(User)] == ["boss@example.com"]
        with app.state.tenants.get("northwind").sessions() as db:
            assert db.query(User).count() == 0
    finally:
        app.state.tenants.close()


def test_a_new_company_speaks_in_general_terms_until_it_says_otherwise(client, ana):
    """Settings → Terms: general words for a new company; its own once set."""
    org = client.get("/auth/me", headers=ana).json()["org"]
    assert org["terms"]["visited"] == {"one": "Account", "many": "Accounts"} and org["terms"]["visitedType"] is None
    terms = client.get("/admin/terms", headers=ana).json()
    assert terms["pharma"]["visited"]["many"] == "Doctors"
    # The Doctor type is there, switched off, for a company that wants it.
    assert client.put("/admin/terms", headers=ana, json={**terms["pharma"], "visitedType": "nope"}).status_code == 422
    saved = client.put("/admin/terms", headers=ana, json=terms["pharma"])
    assert saved.status_code == 200, saved.text
    org = client.get("/auth/me", headers=ana).json()["org"]
    assert org["terms"]["visited"]["many"] == "Doctors" and org["terms"]["site"] == "Clinic"
    measures = {m["key"]: m["label"] for m in client.get("/kpis?all=1", headers=ana).json()["measures"]}
    assert measures["doctors_visited"] == "Doctors visited"
