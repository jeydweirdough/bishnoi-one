import json

import pytest
from fastapi.testclient import TestClient

from app import security
from app.config import Settings
from app.keys import new_private_pem
from app.main import create_app
from app.models import Base
from app.routers import auth
from app.seed import DEMO_PASSWORD, seed_demo_catalog, seed_demo_people, seed_demo_records, seed_reference
from app.store.files import FileStore
from app.store.local import LocalBackend
from app.store.records import Records

security.BCRYPT_ROUNDS = 4
SIGNING_KEY = new_private_pem()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        jwt_private_key=SIGNING_KEY,
        database_url=f"sqlite:///{(tmp_path / 'accounts.db').as_posix()}",
        allowed_hosts=["testserver", "localhost", "127.0.0.1"],
        # Tests fire requests faster than any person; the limits are tested on their own.
        rate_limit_enabled=False,
    )


@pytest.fixture
def records() -> Records:
    return Records(LocalBackend(None))


@pytest.fixture
def files() -> FileStore:
    return FileStore(None)


def build_app(settings, records, files):
    app = create_app(settings, records, files)
    Base.metadata.create_all(app.state.sessions.kw["bind"])
    with app.state.sessions() as db:
        seed_reference(db)
        seed_demo_people(db)
        seed_demo_records(records, db, settings)
        seed_demo_catalog(db, settings)
    auth._attempts.clear()
    return app


@pytest.fixture
def app(settings, records, files):
    return build_app(settings, records, files)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def as_(client):
    """as_("ana") -> headers for Ana, signed in."""
    cache: dict[str, dict] = {}

    def headers(who: str) -> dict:
        if who not in cache:
            r = client.post("/auth/login", json={"email": f"{who}@pharmacrm.test", "password": DEMO_PASSWORD})
            assert r.status_code == 200, r.text
            cache[who] = {"Authorization": f"Bearer {r.json()['accessToken']}"}
        return cache[who]

    return headers


def names(items: list[dict]) -> set[str]:
    return {i["name"] for i in items}


PDF = b"%PDF-1.4\n% a guarantee letter\n%%EOF\n"


def customer_id(client, headers: dict, module: str, name: str) -> str:
    """One customer by name. The list spans every division this person sells
    in, so `module` narrows it — two divisions may hold the same name."""
    r = client.get("/sales/customers", params={"q": name, "division": module}, headers=headers)
    assert r.status_code == 200, r.text
    return next(c["id"] for c in r.json()["items"] if c["name"] == name)


def price_list(client, headers: dict, customer: str) -> dict:
    r = client.get(f"/sales/customers/{customer}/price-list", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def a_customer(client, headers: dict, division: str, team: str | None = None) -> str:
    """Any customer the caller can see there. A price list belongs to a
    customer, so reading one needs somebody to read it for."""
    params = {"division": division, "limit": 1}
    if team:
        params["team"] = team
    r = client.get("/sales/customers", params=params, headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, f"no customer in {division}{'/' + team if team else ''} to read a price list through"
    return items[0]["id"]


def price_list_in(client, headers: dict, division: str, team: str | None = None) -> dict:
    """What a division (or one of its teams) quotes with."""
    return price_list(client, headers, a_customer(client, headers, division, team))


def product_ids(client, headers: dict, module: str) -> dict[str, str]:
    """What this division quotes with. A price list belongs to a customer now
    (its division and team decide the prices), so this asks through the first
    customer the caller can see there."""
    return {p["code"]: p["id"] for p in price_list_in(client, headers, module)["products"]}


def preview_quote(client, headers: dict, customer: str, quote: dict):
    """What the quote would come to. Priced with the customer's own division
    and team, so there is no second place for them to be named."""
    return client.post(f"/sales/customers/{customer}/quotes/preview", json=quote, headers=headers)


def post_quote(client, headers: dict, module: str, customer: str, quote: dict, letter: bytes | None = None):
    """Sends a quote the way the web app does: multipart, JSON in `quote`, the letter as a file.

    `module` is kept for readability at the call sites; the division comes from
    the customer, which is the only place it can disagree."""
    files ={"letterFile": ("letter.pdf", letter, "application/pdf")} if letter is not None else None
    return client.post(
        f"/sales/customers/{customer}/quotes", data={"quote": json.dumps(quote)}, files=files, headers=headers
    )


def field_messages(response) -> dict[str, str]:
    """{"lines.0.productId": "..."} from a 422, the way the web app reads it."""
    return {".".join(str(p) for p in item["loc"][1:]): item["msg"] for item in response.json()["detail"]}


# The second company, for tests that need an outsider. Kept here so any test can ask for it.
ACME = "00000000-0000-4000-8000-0000000000ac"
ACME_CUSTOMER = "Acme Hardware Depot"
ACME_PRODUCT = "ACME-BOLT"


@pytest.fixture
def acme(app, client):
    """Acme: same divisions, teams and roles as Getmeds, its own people, one customer and one product."""
    from app.models import Organization
    from app.modules import ALL_MODULES
    from app.seed import add_person, seed_reference

    with app.state.sessions() as db:
        db.add(Organization(id=ACME, slug="acme", name="Acme Supplies", brand_name="Acme", template="generic_b2b"))
        db.commit()
        seed_reference(db, ACME)
        # Everything a person can be given, so a walk of the screens reaches every one.
        olga = [("admin", ALL_MODULES, None, None), ("executive", ALL_MODULES, None, None), ("division_head", "bnb", "bnb", None)]
        olga += [("department_staff", m, None, None) for m in ("finance", "inventory")]
        add_person(db, "olga@acme.test", "Olga Ortiz", DEMO_PASSWORD, olga)
        add_person(db, "rick@acme.test", "Rick Ramos", DEMO_PASSWORD, [("rep", "bnb", "bnb", "md-telesales")])
    r = client.post("/auth/login", json={"email": "olga@acme.test", "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['accessToken']}"}
    r = client.post(
        "/sales/customers",
        json={"division": "bnb", "team": "md-telesales", "name": ACME_CUSTOMER, "kind": "company"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    r = client.post("/inventory/products", json={"code": ACME_PRODUCT, "name": "Hex bolt", "unit": "Box of 50"}, headers=headers)
    assert r.status_code == 201, r.text
    return headers
