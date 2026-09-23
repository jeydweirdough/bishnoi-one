"""Companies are walled off from each other.

A second company, Acme, is set up next to Getmeds with the same division and
role codes. Nothing of one may show up in, or be changed from, the other:
not through any screen, not by guessing an id, not through the records store
or the files, and not by a forgotten company on a database session.
"""

import re
from datetime import UTC, datetime

import jwt
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, func, select

from app.config import API_DIR
from app.db import make_engine
from app.models import SHARED_TABLES, Base, Division, Membership, Organization, Profile, Role
from app.modules import ALL_MODULES, DEFAULT_ROLES, MODULES
from app.scope import Scope
from app.security import issue_token
from app.seed import DEMO_CUSTOMERS, DEMO_PASSWORD, DEMO_PRODUCTS, add_person
from app.store.files import FileStore
from app.store.local import LocalBackend
from app.store.query import Query
from app.store.records import Create, Delete, Patch, Records
from app.tenancy import FIRST_ORG_ID, TenancyError, all_companies, set_company
from tests.conftest import ACME, ACME_CUSTOMER, ACME_PRODUCT, customer_id

GETMEDS_MARKS = ["pharmacrm.test", *(c[2] for c in DEMO_CUSTOMERS), *(p[0] for p in DEMO_PRODUCTS)]
ACME_MARKS = ["acme.test", ACME_CUSTOMER, ACME_PRODUCT, "Olga Ortiz"]


def sign_in(client, email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def get_routes(app) -> list[str]:
    """Every GET route, with {module} filled in for each module; routes needing an id are tested separately."""
    urls = []
    for path, operations in app.openapi()["paths"].items():
        if "get" not in operations or path == "/health":
            continue
        params = re.findall(r"{(\w+)}", path)
        if params == ["module"]:
            urls += [path.replace("{module}", m.key) for m in MODULES]
        elif not params:
            urls.append(path)
    return urls


# --- the schema ------------------------------------------------------------------------


def test_every_company_table_carries_the_company_in_its_keys_and_links():
    company_tables = {t.name for t in Base.metadata.sorted_tables} - SHARED_TABLES
    for table in Base.metadata.sorted_tables:
        if table.name in SHARED_TABLES:
            assert "org_id" not in table.c, table.name
            continue
        org = table.c.org_id
        assert not org.nullable and {fk.target_fullname for fk in org.foreign_keys} >= {"organizations.id"}, table.name
        pk = [c.name for c in table.primary_key.columns]
        # The company leads the key; or the key is a globally unique id, or starts with the id
        # of a company row it's linked to through the company (a product's prices).
        linked_ids = {tuple(fk.column_keys) for fk in table.foreign_key_constraints}
        assert pk[0] == "org_id" or pk == ["id"] or ("org_id", pk[0]) in linked_ids, (table.name, pk)
        for fk in table.foreign_key_constraints:
            if fk.referred_table.name in company_tables:
                assert "org_id" in fk.column_keys, (table.name, fk.column_keys)
                assert "org_id" in [e.column.name for e in fk.elements], (table.name, fk.referred_table.name)
        for unique in (c for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"):
            assert "org_id" in unique.columns, (table.name, [c.name for c in unique.columns])


# --- the wall on the database session -----------------------------------------------


def test_a_session_without_a_company_is_refused(app):
    with app.state.sessions() as db:
        with pytest.raises(TenancyError):
            db.scalars(select(Division)).all()
        with pytest.raises(TenancyError):
            db.scalar(select(func.count()).select_from(Role))
        with all_companies(db):
            assert db.scalars(select(Division)).all()
        # People are shared: no company needed.
        assert db.scalars(select(Profile)).all()


def test_the_app_builds_no_statement_the_wall_cant_see():
    """A Core exists() built from bare columns escapes the wall; select(...).exists() doesn't."""
    bare_exists = re.compile(r"(?<![.\w`])exists\(")
    found = [
        f"{p.name}:{n}"
        for p in sorted((API_DIR / "app").rglob("*.py"))
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if bare_exists.search(line) and not line.lstrip().startswith("#")
    ]
    assert found == []


def test_subqueries_and_joins_are_walled_too(app, acme):
    with app.state.sessions() as db:
        set_company(db, ACME)
        acme_people = set(db.scalars(select(Profile.email).where(Profile.id.in_(select(Membership.user_id)))))
        assert acme_people == {"olga@acme.test", "rick@acme.test"}
        joined = set(db.scalars(select(Profile.email).join(Membership, Membership.user_id == Profile.id)))
        assert joined == acme_people
        nested = select(Division.code).subquery()
        assert db.scalar(select(func.count()).select_from(nested)) == len([m for m in MODULES if m.is_division])


def test_the_same_codes_live_in_both_companies_without_mixing(app, acme):
    with app.state.sessions() as db:
        with all_companies(db):
            assert db.scalar(select(func.count()).select_from(Division).where(Division.code == "bnb")) == 2
        set_company(db, ACME)
        assert db.scalar(select(func.count()).select_from(Division).where(Division.code == "bnb")) == 1
        assert db.scalar(select(func.count()).select_from(Role)) == len(DEFAULT_ROLES)
        assert {d.org_id for d in db.scalars(select(Division))} == {ACME}
        assert db.get(Division, {"org_id": FIRST_ORG_ID, "code": "bnb"}) is None
        assert db.get(Division, {"org_id": ACME, "code": "bnb"}) is not None


def test_rows_of_another_company_cant_be_written(app, acme):
    with app.state.sessions() as db:
        set_company(db, ACME)
        with all_companies(db):
            theirs = db.get(Division, {"org_id": FIRST_ORG_ID, "code": "bnb"})
        theirs.name = "Taken over"
        with pytest.raises(TenancyError):
            db.flush()
        db.rollback()

        db.add(Role(org_id=FIRST_ORG_ID, key="spy", name="Spy"))
        with pytest.raises(TenancyError):
            db.flush()
        db.rollback()

        mine = Role(key="helper", name="Helper")
        db.add(mine)
        db.flush()
        assert mine.org_id == ACME


# --- through the API -----------------------------------------------------------------


def test_nothing_of_one_company_shows_in_the_other(app, client, as_, acme):
    walkers = [("olga", acme, GETMEDS_MARKS)] + [(who, as_(who), ACME_MARKS) for who in ("carmen", "ramon", "lorna", "joy", "iris")]
    for who, headers, foreign in walkers:
        for url in get_routes(app):
            r = client.get(url, headers=headers)
            assert r.status_code != 500, (who, url, r.text)
            leaked = [mark for mark in foreign if mark in r.text]
            assert not leaked, (who, url, leaked)


def test_ids_from_another_company_find_nothing(client, as_, acme):
    lorna, iris = as_("lorna"), as_("iris")
    alma = customer_id(client, lorna, "bnb", "Dr. Alma Dizon")
    ana = next(u["id"] for u in client.get("/admin/users", headers=as_("carmen")).json() if u["email"] == "ana@pharmacrm.test")
    product = next(p["id"] for p in client.get("/inventory/products", headers=iris).json() if p["code"] == "AMOX-500")

    assert client.get(f"/sales/customers/{alma}", headers=acme).status_code == 404
    assert client.patch(f"/sales/customers/{alma}", json={"name": "Taken over"}, headers=acme).status_code == 404
    assert client.delete(f"/sales/customers/{alma}", headers=acme).status_code == 404
    assert client.get(f"/inventory/products/{product}", headers=acme).status_code == 404
    assert client.patch(f"/inventory/products/{product}", json={"name": "Taken over"}, headers=acme).status_code == 404
    assert client.get(f"/admin/users/{ana}", headers=acme).status_code == 404
    assert client.patch(f"/admin/users/{ana}", json={"password": "a-new-password-1"}, headers=acme).status_code == 404
    grant = {"roleKey": "rep", "moduleKey": "bnb", "divisionCode": "bnb", "subdivisionCode": "general"}
    assert client.post(f"/admin/users/{ana}/assignments", json=grant, headers=acme).status_code == 404

    r = client.post("/sales/bulk/customers", json={"action": "status", "status": "inactive", "ids": [alma]}, headers=acme)
    assert r.status_code == 202, r.text
    assert r.json()["succeeded"] == 0

    after = client.get(f"/sales/customers/{alma}", headers=lorna).json()
    assert after["name"] == "Dr. Alma Dizon" and after["status"] == "active"
    assert client.get(f"/inventory/products/{product}", headers=iris).json()["name"] == "Amoxicillin 500 mg"


def test_a_person_in_two_companies_works_in_one_at_a_time(app, client, as_, acme):
    getmeds = as_("ana")  # signs in to Getmeds, her only company so far
    with app.state.sessions() as db:
        set_company(db, ACME)
        added = add_person(db, "ana@pharmacrm.test", "Ana Reyes", "ignored-password", [("rep", "bnb", "bnb", "general")])
        assert added is not None

    # Her Getmeds password still works; she lands where she worked last.
    headers = sign_in(client, "ana@pharmacrm.test")
    me = client.get("/auth/me", headers=headers).json()
    assert me["org"]["name"] == "Getmeds"
    companies = client.get("/auth/orgs", headers=headers).json()
    assert [c["name"] for c in companies["items"]] == ["Getmeds", "Acme Supplies"]

    r = client.post("/auth/switch-org", json={"orgId": ACME}, headers=headers)
    assert r.status_code == 200, r.text
    in_acme = {"Authorization": f"Bearer {r.json()['accessToken']}"}
    me = client.get("/auth/me", headers=in_acme).json()
    assert me["org"]["name"] == "Acme Supplies"
    assert [(m["key"], [t["code"] for t in m["teams"]]) for m in me["modules"] if m["kind"] != "app"] == [("bnb", ["general"])]
    customers = client.get("/sales/customers?division=bnb", headers=in_acme).json()["items"]
    assert [c["name"] for c in customers] == []  # Acme's only customer is in MD Telesales

    # Acme's admin can switch her off in Acme only, and can't touch her password or name.
    assert client.patch(f"/admin/users/{me['user']['id']}", json={"password": "a-new-password-1"}, headers=acme).status_code == 409
    assert client.patch(f"/admin/users/{me['user']['id']}", json={"fullName": "Someone Else"}, headers=acme).status_code == 409
    assert client.patch(f"/admin/users/{me['user']['id']}", json={"isActive": False}, headers=acme).status_code == 200
    assert client.get("/auth/me", headers=in_acme).status_code == 401
    assert client.get("/auth/me", headers=getmeds).status_code == 200
    assert client.post("/auth/switch-org", json={"orgId": ACME}, headers=getmeds).status_code == 404

    # Someone only in Acme is Acme's to manage.
    rick = next(u["id"] for u in client.get("/admin/users", headers=acme).json() if u["email"] == "rick@acme.test")
    assert client.patch(f"/admin/users/{rick}", json={"password": "a-new-password-1"}, headers=acme).status_code == 200


def test_the_admin_list_holds_only_the_companys_people(client, as_, acme):
    acme_people = {u["email"] for u in client.get("/admin/users", headers=acme).json()}
    assert acme_people == {"olga@acme.test", "rick@acme.test"}
    getmeds_people = {u["email"] for u in client.get("/admin/users", headers=as_("carmen")).json()}
    assert not any(e.endswith("@acme.test") for e in getmeds_people)


def test_adding_someone_who_has_an_account_elsewhere_keeps_their_password(client, as_, acme):
    r = client.post("/admin/users", json={"email": "ben@pharmacrm.test", "fullName": "Ben Cruz", "password": "acme-chose-this-1"}, headers=acme)
    assert r.status_code == 201, r.text
    assert r.json()["existingAccount"] is True
    assert client.post("/auth/login", json={"email": "ben@pharmacrm.test", "password": "acme-chose-this-1"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ben@pharmacrm.test", "password": DEMO_PASSWORD}).status_code == 200
    again = client.post("/admin/users", json={"email": "ben@pharmacrm.test", "fullName": "Ben Cruz", "password": "whatever-123"}, headers=acme)
    assert again.status_code == 409


def test_a_suspended_company_signs_everyone_out(app, client, acme):
    with app.state.sessions() as db:
        db.get(Organization, ACME).status = "suspended"
        db.commit()
    assert client.get("/auth/me", headers=acme).status_code == 401
    assert client.post("/auth/login", json={"email": "olga@acme.test", "password": DEMO_PASSWORD}).status_code == 403


def test_tokens_must_name_a_company_the_person_is_in(app, client, settings, acme):
    with app.state.sessions() as db:
        carmen = db.scalar(select(Profile).where(Profile.email == "carmen@pharmacrm.test"))
    token, _ = issue_token(settings, carmen, ACME, "no-such-session")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    # A token from before there were companies: sign in again.
    now = int(datetime.now(UTC).timestamp())
    old = jwt.encode(
        {"sub": carmen.id, "email": carmen.email, "aud": settings.jwt_audience, "iss": settings.jwt_issuer,
         "role": "authenticated", "iat": now, "exp": now + 3600},
        "x" * 48,  # the old shared-secret kind; Orbit only takes its own signature now
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


# --- the records store and files ---------------------------------------------------------

SCOPE = Scope("bnb", "general")


def customer(doc_id: str) -> dict:
    return {"_id": doc_id, "_type": "customer", "name": doc_id, **SCOPE.stamp()}


def test_the_records_store_keeps_companies_apart():
    backend = LocalBackend(None)
    getmeds, acme = Records(backend).for_org(FIRST_ORG_ID), Records(backend).for_org(ACME)
    getmeds.commit([Create(customer("g1"))])
    assert backend._docs["g1"]["orgId"] == FIRST_ORG_ID

    assert acme.find(Query("customer", {SCOPE})) == []
    assert acme.count(Query("customer", {SCOPE})) == 0
    assert acme.get("customer", "g1", frozenset({SCOPE})) is None
    with pytest.raises(TenancyError):
        acme.commit([Patch("g1", {"name": "Taken over"})])
    with pytest.raises(TenancyError):
        acme.commit([Delete("g1")])
    with pytest.raises(TenancyError):
        acme.commit([Create({**customer("a1"), "orgId": FIRST_ORG_ID})])
    with pytest.raises(ValueError):
        getmeds.commit([Patch("g1", {"orgId": ACME})])
    with pytest.raises(TenancyError):
        getmeds.find(Query("customer", {SCOPE}, org_id=ACME))
    with pytest.raises(TenancyError):
        getmeds.for_org(ACME)
    with pytest.raises(TenancyError):
        Records(backend).find(Query("customer", {SCOPE}))
    assert backend._docs["g1"]["name"] == "g1"


def test_a_record_of_another_company_is_dropped_even_if_the_store_returns_it():
    class Leaky(LocalBackend):
        def fetch(self, query):  # ignores the company, as a buggy query might
            return [d for d in self._docs.values() if d["_type"] == query.doc_type]

    backend = Leaky(None)
    Records(backend).for_org(FIRST_ORG_ID).commit([Create(customer("g1"))])
    assert Records(backend).for_org(ACME).find(Query("customer", {SCOPE})) == []


@pytest.mark.parametrize("on_disk", [False, True])
def test_files_stay_in_their_company(tmp_path, on_disk):
    store = FileStore(tmp_path if on_disk else None)
    ref = store.for_org(FIRST_ORG_ID).put(b"%PDF-1.4 letter")
    assert store.for_org(FIRST_ORG_ID).read(ref) == b"%PDF-1.4 letter"
    assert store.for_org(ACME).read(ref) is None
    store.for_org(ACME).delete(ref)
    assert store.for_org(FIRST_ORG_ID).read(ref) == b"%PDF-1.4 letter"
    with pytest.raises(TenancyError):
        store.read(ref)


def test_files_from_before_companies_move_into_the_first_one(tmp_path):
    loose = "ab" * 16
    (tmp_path / loose).write_bytes(b"%PDF-old")
    store = FileStore(tmp_path).for_org(FIRST_ORG_ID)
    assert store.adopt_loose_files() == 1
    assert store.read(loose) == b"%PDF-old"
    assert not (tmp_path / loose).exists()


# --- the upgrade ------------------------------------------------------------------------


def test_the_upgrade_moves_everything_into_the_first_company(tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    config = Config(str(API_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    command.upgrade(config, "0004")

    now = datetime.now(UTC)
    engine = make_engine(url)
    with engine.begin() as connection:
        tables = MetaData()
        table = lambda name: Table(name, tables, autoload_with=connection)  # noqa: E731
        connection.execute(table("profiles").insert(), [
            {"id": "p-on", "email": "on@x.test", "full_name": "On", "is_active": True, "created_at": now, "updated_at": now},
            {"id": "p-off", "email": "off@x.test", "full_name": "Off", "is_active": False, "created_at": now, "updated_at": now},
        ])
        connection.execute(table("divisions").insert(), [{"code": "bnb", "name": "B&B", "sort_order": 0}])
        connection.execute(table("subdivisions").insert(), [
            {"division_code": "bnb", "code": "general", "name": "General", "is_active": True, "sort_order": 0}
        ])
        connection.execute(table("roles").insert(), [{"key": "clerk", "name": "Clerk", "description": "", "sort_order": 9}])
        connection.execute(table("assignments").insert(), [
            {"id": "a1", "user_id": "p-on", "role_key": "clerk", "module_key": "bnb", "division_code": "bnb",
             "subdivision_code": "general", "created_at": now}
        ])
        connection.execute(table("products").insert(), [
            {"id": "prod-1", "code": "X-1", "name": "Thing", "unit": "Box", "is_active": True, "created_at": now, "updated_at": now}
        ])

    command.upgrade(config, "head")

    with engine.connect() as connection:
        tables = MetaData()
        table = lambda name: Table(name, tables, autoload_with=connection)  # noqa: E731
        orgs = connection.execute(select(table("organizations").c.slug)).scalars().all()
        assert orgs == ["getmeds"]
        memberships = dict(connection.execute(select(table("memberships").c.user_id, table("memberships").c.status)).all())
        assert memberships == {"p-on": "active", "p-off": "suspended"}
        assert set(connection.execute(select(table("profiles").c.is_active)).scalars()) == {True}
        for name in ("divisions", "subdivisions", "roles", "assignments", "products"):
            assert set(connection.execute(select(table(name).c.org_id)).scalars()) == {FIRST_ORG_ID}, name
        assert connection.execute(select(table("assignments").c.role_key)).scalar() == "clerk"
        assert connection.execute(select(table("products").c.code)).scalar() == "X-1"
