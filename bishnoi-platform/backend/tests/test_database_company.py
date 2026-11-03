"""Single-company service ownership is derived from and pinned in Platform data."""
from sqlalchemy import select
from app.models import Application, Company, CompanyApp, AuditEntry
from tests.conftest import make_company, app_id
from tests.test_connections import connect, asks


def test_one_company_is_derived_once_and_data_key_remains_stable(client, ana, app):
    company = make_company(client, ana, name="First company", apps=("finance",))
    key = connect(client, ana, "finance")
    first = asks(client, key)
    assert first.status_code == 200, first.text
    first = first.json()
    assert first["databaseCompany"]["id"] == company["id"]
    assert first["databaseCompany"]["slug"] == company["slug"]
    make_company(client, ana, name="Second company", apps=("finance",))
    second = asks(client, key).json()
    assert second["databaseCompany"]["id"] == company["id"]
    assert second["dataKey"] == first["dataKey"] and second["dataKey"]
    with app.state.sessions() as db:
        service = db.scalar(select(Application).where(Application.key == "finance"))
        assert service.database_company_id == company["id"]
        assert db.scalar(select(AuditEntry).where(AuditEntry.action == "application.database_bound"))


def test_multiple_companies_require_an_authorized_existing_company_choice(client, ana, ben):
    one = make_company(client, ana, name="First company", apps=("finance",))
    two = make_company(client, ana, name="Second company", apps=("finance",))
    key = connect(client, ana, "finance")
    assert asks(client, key).json()["databaseCompany"] is None
    service = app_id(client, ana, "finance")
    url = f"/platform/applications/{service}"
    assert client.patch(url, headers=ben, json={"databaseCompanyId": one["id"]}).status_code == 403
    assert client.patch(url, headers=ana, json={"databaseCompanyId": "unknown-company"}).status_code == 422
    assert client.patch(url, headers=ana, json={"databaseCompanyId": None}).status_code == 422
    saved = client.patch(url, headers=ana, json={"databaseCompanyId": two["id"]})
    assert saved.status_code == 200, saved.text
    assert saved.json()["application"]["databaseCompanyId"] == two["id"]
    assert asks(client, key).json()["databaseCompany"]["id"] == two["id"]
    other = app_id(client, ana, "crm")
    assert client.patch(f"/platform/applications/{other}", headers=ana, json={"databaseCompanyId": two["id"]}).status_code == 422


def test_company_changes_are_derived_and_revoked_owner_never_rebinds(client, ana, app):
    one = make_company(client, ana, name="First company", apps=("finance",))
    key = connect(client, ana, "finance")
    assert asks(client, key).json()["databaseCompany"]["id"] == one["id"]
    two = make_company(client, ana, name="Second company", apps=("finance",))
    with app.state.sessions() as db:
        company = db.get(Company, one["id"])
        company.slug = "first-renamed"
        company.currency = "USD"
        company.timezone = "Asia/Singapore"
        db.commit()
    current = asks(client, key).json()["databaseCompany"]
    assert (current["slug"], current["currency"], current["timezone"]) == ("first-renamed", "USD", "Asia/Singapore")
    with app.state.sessions() as db:
        service = db.scalar(select(Application).where(Application.key == "finance"))
        db.delete(db.get(CompanyApp, (one["id"], service.id)))
        db.commit()
    assert asks(client, key).json()["databaseCompany"] is None
    with app.state.sessions() as db:
        service = db.scalar(select(Application).where(Application.key == "finance"))
        assert service.database_company_id == one["id"] != two["id"]


def test_unsubscribed_company_cannot_be_selected(client, ana):
    company = make_company(client, ana, name="Not in Finance", apps=("crm",))
    service = app_id(client, ana, "finance")
    assert client.patch(f"/platform/applications/{service}", headers=ana, json={"databaseCompanyId": company["id"]}).status_code == 422
