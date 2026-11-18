"""Approval slips (Step 4C): one request that passes up the org chart, step by step; each step signs or returns it
with a note; the last signature approves; never your own; administrators may act on any step; the app hears the end."""

from datetime import UTC, datetime

from sqlalchemy import select

from modules.platform import approvals, events
from modules.platform.models import (AccessRole, AccessRolePermission, Application, Approval, BusinessEvent, Company, CompanyApp,
                                     EventDelivery, Identity, IdentityApp)
from modules.platform.tests.test_company_access import getmeds, modules, person  # noqa: F401 (fixtures)
from modules.platform.tests.test_unit_heads import unit

PDF = b"%PDF-1.4\n% slip\n%%EOF\n"


def chart(client, getmeds, ana):
    """Sales (head Mia) > Rx team (head Rio) > Jade; the company has Inventory."""
    h = getmeds["owner"]["h"]
    mia = person(client, ana, getmeds["company"], "Mia Mentor", "mia@getmeds.test", apps=(("crm", "Salesperson"),))
    sales = unit(client, h, "department", "Sales", heads=[mia["id"]])
    rx = unit(client, h, "team", "Rx", parent=sales["id"], heads=[getmeds["rio"]["id"]])
    client.put(f"/identity/organisation/people/{getmeds['jade']['id']}", json={"mainUnitId": rx["id"]}, headers=h)
    return mia


def with_inventory(app, getmeds):
    with app.state.sessions() as db:
        inventory = db.scalar(select(Application).where(Application.key == "inventory"))
        if db.get(CompanyApp, (getmeds["company"]["id"], inventory.id)) is None:
            db.add(CompanyApp(company_id=getmeds["company"]["id"], application_id=inventory.id))
            db.commit()


def request(app, getmeds, who="jade", record="so-1", number="SO-000001", **extra) -> str:
    """Inventory asks for a slip, as its business event does."""
    with app.state.sessions() as db:
        company = db.get(Company, getmeds["company"]["id"])
        me = db.get(Identity, getmeds[who]["id"]) if who in getmeds else None
        events.accept(db, "inventory", company, f"ev-{record}-{datetime.now(UTC).timestamp()}", "approval.requested", {
            "kind": "sales_order", "id": record, "number": number, "title": f"Sales order {number}", "url": f"/crm/sales/orders/{record}",
            "summary": {"customer": "Mercury Drug", "totalCentavos": 1_250_000, "currency": "PHP"},
            "requester": {"identityId": me.id if me else None, "email": me.email if me else extra.get("email"), "name": me.full_name if me else "Someone"},
            "attachments": [{"label": "Quote Q-000010", "app": "crm", "kind": "quote", "id": "q-10", "number": "Q-000010", "url": "/crm/quotes/q-10"}],
            **extra,
        }, datetime.now(UTC))
        db.commit()
        return db.scalar(select(Approval.id).where(Approval.record_id == record).order_by(Approval.created_at.desc()).limit(1))


def decided(app) -> list[dict]:
    with app.state.sessions() as db:
        rows = db.execute(select(BusinessEvent, EventDelivery).join(EventDelivery, EventDelivery.event_id == BusinessEvent.id)
                          .where(BusinessEvent.kind == "approval.decided")).all()
        return [{**e.data, "target": d.target} for e, d in rows]


def test_the_slip_passes_up_the_chart_in_order_and_the_last_signature_approves(app, client, ana, getmeds):  # noqa: F811
    mia = chart(client, getmeds, ana)
    with_inventory(app, getmeds)
    jade, rio = getmeds["jade"], getmeds["rio"]
    slip_id = request(app, getmeds)
    slip = client.get(f"/identity/approvals/{slip_id}", headers=jade["h"]).json()
    assert slip["number"] == "AR-000001" and slip["status"] == "pending" and slip["no"] >= 40000001
    assert [(s["label"], s["approver"]["name"]) for s in slip["steps"]] == [("Manager", "Rio Santos"), ("Next manager", "Mia Mentor")]
    assert slip["attachments"][0]["url"] == "/crm/quotes/q-10" and slip["mine"] and not slip["canSign"]

    # Never your own; never out of turn; a stranger doesn't even see it.
    assert client.post(f"/identity/approvals/{slip_id}/sign", json={}, headers=jade["h"]).status_code == 403
    assert client.post(f"/identity/approvals/{slip_id}/sign", json={}, headers=mia["h"]).status_code == 403
    assert [s["id"] for s in client.get("/identity/approvals?box=waiting", headers=rio["h"]).json()["items"]] == [slip_id]
    assert client.get("/identity/approvals?box=waiting", headers=mia["h"]).json()["items"] == []
    assert client.get("/identity/approvals/count", headers=rio["h"]).json() == {"waiting": 1, "any": True}

    r = client.post(f"/identity/approvals/{slip_id}/sign", json={"note": "Stock is there"}, headers=rio["h"])
    assert r.status_code == 200, r.text
    assert r.json()["steps"][0]["status"] == "signed" and r.json()["steps"][0]["actedAs"] == "approver" and r.json()["status"] == "pending"
    assert decided(app) == []
    assert [s["id"] for s in client.get("/identity/approvals?box=waiting", headers=mia["h"]).json()["items"]] == [slip_id]
    r = client.post(f"/identity/approvals/{slip_id}/sign", json={}, headers=mia["h"])
    assert r.json()["status"] == "approved" and r.json()["finishedAt"]
    # Inventory alone hears it, as the last signer.
    [told] = decided(app)
    assert told["target"] == "inventory" and told["decision"] == "approved" and told["id"] == "so-1" and told["by"]["email"] == "mia@getmeds.test"
    assert client.post(f"/identity/approvals/{slip_id}/sign", json={}, headers=mia["h"]).status_code == 409
    assert [s["id"] for s in client.get("/identity/approvals?box=mine", headers=jade["h"]).json()["items"]] == [slip_id]
    assert [s["id"] for s in client.get("/identity/approvals?box=done", headers=rio["h"]).json()["items"]] == [slip_id]
    # The record's slip, for its page.
    found = client.get("/identity/approvals/for?app=inventory&kind=sales_order&id=so-1", headers=jade["h"]).json()
    assert found["slip"]["id"] == slip_id and found["earlier"] == []


def test_returned_with_a_note_then_sent_again_as_a_new_slip(app, client, ana, getmeds):  # noqa: F811
    chart(client, getmeds, ana)
    with_inventory(app, getmeds)
    rio = getmeds["rio"]
    first = request(app, getmeds)
    assert request(app, getmeds) == first  # asked again while it waits: the same slip
    assert client.post(f"/identity/approvals/{first}/return", json={"note": ""}, headers=rio["h"]).status_code == 422
    r = client.post(f"/identity/approvals/{first}/return", json={"note": "Wrong warehouse"}, headers=rio["h"])
    assert r.status_code == 200 and r.json()["status"] == "returned" and [s["status"] for s in r.json()["steps"]] == ["returned", "skipped"]
    [told] = decided(app)
    assert told["decision"] == "returned" and told["note"] == "Wrong warehouse"
    second = request(app, getmeds)
    assert second != first
    again = client.get(f"/identity/approvals/{second}", headers=rio["h"]).json()
    assert again["number"] == "AR-000002" and again["replaces"]["id"] == first and again["replaces"]["note"] == "Wrong warehouse"
    assert len(client.get("/identity/approvals/for?app=inventory&kind=sales_order&id=so-1", headers=rio["h"]).json()["earlier"]) == 1


def test_an_administrator_may_act_on_any_step_but_never_on_their_own(app, client, ana, getmeds):  # noqa: F811
    chart(client, getmeds, ana)
    with_inventory(app, getmeds)
    owner = getmeds["owner"]
    slip_id = request(app, getmeds)
    r = client.post(f"/identity/approvals/{slip_id}/sign", json={}, headers=owner["h"])
    assert r.status_code == 200 and r.json()["steps"][0]["actedAs"] == "administrator" and r.json()["steps"][0]["actedBy"] == "Olive Owner"
    assert [s["id"] for s in client.get("/identity/approvals?box=all", headers=owner["h"]).json()["items"]] == [slip_id]
    # Olive's own request: nobody above her on the chart, so the sales approvers; she can't sign it herself.
    own = request(app, getmeds, who="owner", record="so-2", number="SO-000002")
    slip = client.get(f"/identity/approvals/{own}", headers=owner["h"]).json()
    assert [(s["label"], s["group"]) for s in slip["steps"]] == [("Sales approver", {"app": "inventory", "permission": "sales.approve"})]
    assert client.post(f"/identity/approvals/{own}/sign", json={}, headers=owner["h"]).status_code == 403


def test_a_group_step_is_for_whoever_holds_the_permission(app, client, ana, getmeds):  # noqa: F811
    with_inventory(app, getmeds)
    jade, rio = getmeds["jade"], getmeds["rio"]
    with app.state.sessions() as db:
        inventory = db.scalar(select(Application).where(Application.key == "inventory"))
        role = AccessRole(company_id=getmeds["company"]["id"], name="Sales approver")
        db.add(role)
        db.flush()
        db.add(AccessRolePermission(role_id=role.id, app_key="inventory", permission="sales.approve"))
        db.add(IdentityApp(identity_id=rio["id"], application_id=inventory.id, access_role_id=role.id, granted_by="test"))
        db.commit()
    second = request(app, getmeds, record="so-3", number="SO-000003")  # Jade isn't on the chart
    assert [s["id"] for s in client.get("/identity/approvals?box=waiting", headers=rio["h"]).json()["items"]] == [second]
    r = client.post(f"/identity/approvals/{second}/sign", json={}, headers=rio["h"])
    assert r.json()["status"] == "approved" and r.json()["steps"][0]["actedAs"] == "holder"
    assert client.get("/identity/approvals?box=waiting", headers=jade["h"]).json()["items"] == []


def test_files_are_added_while_it_waits_and_a_withdrawn_slip_is_cancelled(app, client, ana, getmeds):  # noqa: F811
    chart(client, getmeds, ana)
    with_inventory(app, getmeds)
    jade, rio = getmeds["jade"], getmeds["rio"]
    slip_id = request(app, getmeds)
    r = client.post(f"/identity/approvals/{slip_id}/files", files={"file": ("letter.pdf", PDF, "application/pdf")}, data={"label": "Hospital letter"}, headers=jade["h"])
    assert r.status_code == 201, r.text
    item = next(a for a in r.json()["attachments"] if a["kind"] == "file")
    assert item["label"] == "Hospital letter" and item["contentType"] == "application/pdf"
    assert client.get(f"/identity/approvals/{slip_id}/files/{item['id']}", headers=rio["h"]).content == PDF
    bad = client.post(f"/identity/approvals/{slip_id}/files", files={"file": ("x.exe", b"MZ....", "application/octet-stream")}, headers=jade["h"])
    assert bad.status_code == 422
    with app.state.sessions() as db:
        events.accept(db, "inventory", db.get(Company, getmeds["company"]["id"]), "ev-withdraw", "approval.withdrawn",
                      {"kind": "sales_order", "id": "so-1", "reason": "Cancelled in Inventory"}, datetime.now(UTC))
        db.commit()
    slip = client.get(f"/identity/approvals/{slip_id}", headers=jade["h"]).json()
    assert slip["status"] == "cancelled" and slip["note"] == "Cancelled in Inventory" and decided(app) == []
    assert client.post(f"/identity/approvals/{slip_id}/sign", json={}, headers=rio["h"]).status_code == 409


def test_signing_keeps_the_signers_platform_signature(app, client, ana, getmeds):  # noqa: F811
    from modules.platform import signatures
    from modules.platform.accounts import account_of
    from modules.platform.tests.test_signatures import png

    chart(client, getmeds, ana)
    with_inventory(app, getmeds)
    with app.state.sessions() as db:
        account = account_of(db, db.get(Identity, getmeds["rio"]["id"]))
        signatures.keep(db, account.id, signatures.checked_png(png()), "drawn")
        db.commit()
    slip_id = request(app, getmeds)
    r = client.post(f"/identity/approvals/{slip_id}/sign", json={}, headers=getmeds["rio"]["h"]).json()
    assert r["steps"][0]["signature"].startswith("data:image/png;base64,") and r["steps"][1]["signature"] is None
    with app.state.sessions() as db:
        assert approvals.current(db, db.get(Approval, slip_id)).label == "Next manager"


def test_a_sales_order_goes_up_the_chart_and_comes_back_approved_in_process(tmp_path, monkeypatch):
    """The real Platform and Inventory in one backend: Inventory's submit opens the slip, the coach signs it, and
    Inventory confirms the order as the coach."""
    from fastapi.testclient import TestClient

    from modules import inprocess
    from modules.inventory import business_events as inventory_events
    from modules.inventory.config import Settings as InventorySettings
    from modules.inventory.main import create_app as inventory_app
    from modules.inventory.models import Role, SalesOrder, User as InventoryUser
    from modules.inventory.security import hash_password as inventory_hash
    from modules.platform import addresses
    from modules.platform.config import Settings as PlatformSettings
    from modules.platform.main import create_app as platform_app
    from modules.platform.models import User
    from modules.platform.security import hash_password
    from modules.platform.tests.conftest import PASSWORD, bearer, make_company, sign_in

    base, hosts = "http://127.0.0.1:8300", ["testserver", "127.0.0.1"]
    (tmp_path / "platform").mkdir()
    (tmp_path / "inventory").mkdir()
    platform = platform_app(PlatformSettings(_env_file=None, allowed_hosts=hosts, backend_url=base,
                                             database_url=f"sqlite:///{(tmp_path / 'platform' / 'test.db').as_posix()}"))
    with platform.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.commit()
    monkeypatch.setattr(events, "kick", lambda sessions, s: _deliver(sessions, s))
    inventory = inventory_app(InventorySettings(_env_file=None, allowed_hosts=hosts,
                                                database_url=f"sqlite:///{(tmp_path / 'inventory' / 'test.db').as_posix()}"))
    try:
        with TestClient(platform) as pc:
            ana = bearer(sign_in(pc))
            company = make_company(pc, ana, apps=("inventory",))
            assert company["slug"] == "getmeds"
            jade = person(pc, ana, company, "Jade Madigal", "jade@getmeds.test")
            rio = person(pc, ana, company, "Rio Santos", "rio@getmeds.test")
            owner = person(pc, ana, company, "Olive Owner", "olive@getmeds.test", admin=True)
            team = unit(pc, owner["h"], "team", "Rx", heads=[rio["id"]])
            pc.put(f"/identity/organisation/people/{jade['id']}", json={"mainUnitId": team["id"]}, headers=owner["h"])
            key = pc.get("/pass/key").json()["publicKey"]
        with TestClient(inventory) as ic:
            tenant = inventory.state.tenants.get("getmeds").sessions
            with tenant() as db:
                admin = db.scalar(select(Role.id).where(Role.name == "Administrator"))
                sales = db.scalar(select(Role.id).where(Role.name == "Sales"))
                db.add(InventoryUser(email="ana@example.com", full_name="Ana", password_hash=inventory_hash(PASSWORD), role_id=admin))
                db.add(InventoryUser(email="jade@getmeds.test", full_name="Jade Madigal", password_hash=inventory_hash(PASSWORD), role_id=sales,
                                     platform_identity_id=jade["id"]))
                db.add(InventoryUser(email="rio@getmeds.test", full_name="Rio Santos", password_hash=inventory_hash(PASSWORD), role_id=sales,
                                     platform_identity_id=rio["id"]))
                db.commit()
            ia = bearer(ic.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}))
            ij = bearer(ic.post("/auth/login", json={"email": "jade@getmeds.test", "password": PASSWORD}))
            ic.post("/inventory/warehouses", json={"code": "MNL", "name": "Manila"}, headers=ia)
            gloves = ic.post("/inventory/products", json={"sku": "GLV-M", "name": "Gloves M", "unitCode": "box", "costPrice": 100, "sellingPrice": 200}, headers=ia).json()["id"]
            # Now connected to the Platform of this backend.
            inventory.state.settings.platform_api_url = f"{base}/platform"
            inventory.state.settings.platform_public_key = key
            inventory.state.settings.platform_app_key = None
            monkeypatch.setitem(inventory_events._state, "settings", None)  # sent below, not on a thread
            monkeypatch.setattr("modules.inventory.platform_connect.connect_key", lambda settings: "in-process")
            inprocess.register(base, "platform", "/platform", platform)
            inprocess.register(base, "inventory", "/inventory", inventory)
            made = ic.post("/inventory/sales-orders", json={"customerName": "PGH", "lines": [{"productId": gloves, "quantity": 3}]}, headers=ij).json()
            assert ic.post(f"/inventory/sales-orders/{made['id']}/submit", headers=ij).status_code == 200
            with tenant() as db:
                assert inventory_events.flush(db, inventory.state.settings) >= 1
        with TestClient(platform) as pc:
            [slip] = pc.get("/identity/approvals?box=waiting", headers=rio["h"]).json()["items"]
            assert slip["record"]["number"] == made["number"] and slip["requestedBy"]["name"] == "Jade Madigal"
            assert pc.post(f"/identity/approvals/{slip['id']}/sign", json={}, headers=jade["h"]).status_code == 403
            assert pc.post(f"/identity/approvals/{slip['id']}/sign", json={}, headers=rio["h"]).json()["status"] == "approved"
        with tenant() as db:
            order = db.get(SalesOrder, made["id"])
            assert order.status == "confirmed" and order.decided_by.email == "rio@getmeds.test"
    finally:
        inprocess.clear()
        addresses.configure(None)
        platform.state.sessions.kw["bind"].dispose()
        inventory.state.tenants.close()


def _deliver(sessions, settings):
    with sessions() as db:
        events.deliver_due(db, settings)
