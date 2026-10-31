"""Connected to Bishnoi One, Inventory's settings (categories, brands, units, couriers, warehouses and their
locations) are changed only by the company's administrators (2026-10-31). Standalone, as before."""

from sqlalchemy import select

from app.models import Role, RolePermission
from tests.test_company import platform  # noqa: F401 (fixture: a stand-in Platform)


def test_connected_only_the_administrator_changes_a_setting(app, client, people, platform):  # noqa: F811
    with app.state.sessions() as db:
        warehouse = db.scalar(select(Role.id).where(Role.name == "Warehouse"))
        for p in ("warehouses.manage", "products.create"):
            if not db.get(RolePermission, (warehouse, p)):
                db.add(RolePermission(role_id=warehouse, permission=p))
        db.commit()
    wes, ana = people["wes"], people["ana"]
    for path, body in (("/inventory/warehouses", {"code": "DVO", "name": "Davao"}), ("/inventory/categories", {"name": "Vaccines"}),
                       ("/inventory/couriers", {"code": "GRAB", "name": "Grab Express"})):
        refused = client.post(path, json=body, headers=wes)
        assert refused.status_code == 403 and "administrators" in refused.json()["detail"], (path, refused.text)
        assert client.post(path, json=body, headers=ana).status_code == 201, path
    assert client.get("/inventory/warehouses", headers=wes).status_code == 200  # reading is never limited
