"""Connected to Bishnoi One, Finance's settings (taxes, number series, default accounts, expense categories,
automatic invoicing) are changed only by the company's administrators (2026-10-31). Standalone, as before."""

from sqlalchemy import select

from app.models import RolePermission, User
from .test_tax_api import ana, app, ben, client  # noqa: F401 (fixtures)


def test_connected_only_the_administrator_changes_a_setting(app, client, ana, ben):  # noqa: F811 (fixtures)
    with app.state.sessions() as db:
        role = db.scalar(select(User.role_id).where(User.email == "ben@example.com"))
        db.add(RolePermission(role_id=role, permission="categories.manage"))
        db.commit()
    # A category needs the expense account its receipts post to.
    account = next(a for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"] if a["code"] == "6900")["id"]
    # Standalone: the permission is enough.
    assert client.post("/finance/funds/categories", json={"name": "Meals", "accountId": account}, headers=ben).status_code == 201
    app.state.settings.platform_api_url = "http://platform.test"
    try:
        refused = client.post("/finance/funds/categories", json={"name": "Travel", "accountId": account}, headers=ben)
        assert refused.status_code == 403 and "administrators" in refused.json()["detail"]
        assert client.post("/finance/funds/categories", json={"name": "Travel", "accountId": account}, headers=ana).status_code == 201
    finally:
        app.state.settings.platform_api_url = None
