"""Finance's roles: each action needs its permission, the Administrator runs
users and roles, and every change is in the activity log."""

from app.models import User
from app.permissions import ROLE_AUDITOR_ID
from app.security import hash_password

from .test_ledger import accounts
from .test_tax_api import PASSWORD, REGISTRATION, app, ana, ben, bearer, client, sign_in  # noqa: F401 (fixtures)


def auditor(app, client) -> dict:
    with app.state.sessions() as db:
        db.add(User(email="aud@example.com", full_name="Aud Itor", password_hash=hash_password(PASSWORD), role_id=ROLE_AUDITOR_ID))
        db.commit()
    return bearer(sign_in(client, "aud@example.com"))


def test_staff_do_the_days_work_but_not_the_setup(client, ana, ben):  # noqa: F811 (fixtures)
    acc = accounts(client, ana)
    # Staff read everything, and post journals.
    assert client.get("/finance/ledger/accounts", headers=ben).json()["canEdit"] is False
    assert client.get("/tax/setup", headers=ben).json()["canEdit"] is False
    # The setup is the Administrator's.
    new = {"code": "6150", "name": "Representation", "type": "expense"}
    assert client.post("/finance/ledger/accounts", json=new, headers=ben).status_code == 403
    assert client.put("/finance/ledger/posting", json={"accounts": {"cash_account_id": acc["1010"]["id"]}}, headers=ben).status_code == 403
    assert client.put("/tax/profile", json=REGISTRATION, headers=ben).status_code == 403
    assert client.post("/finance/ledger/accounts", json=new, headers=ana).status_code == 201
    # Users, roles and the log too.
    for path in ("/admin/users", "/admin/roles", "/admin/audit"):
        assert client.get(path, headers=ben).status_code == 403
        assert client.get(path, headers=ana).status_code == 200


def test_the_auditor_sees_and_changes_nothing(app, client, ana):  # noqa: F811 (fixtures)
    aud = auditor(app, client)
    assert client.get("/finance/ledger/trial-balance", headers=aud).status_code == 200
    assert client.get("/finance/funds", headers=aud).status_code == 200
    assert client.get("/admin/audit", headers=aud).status_code == 200
    line = {"accountId": accounts(client, ana)["1010"]["id"], "debitCentavos": 100}
    assert client.post("/finance/ledger/entries", json={"date": "2026-01-02", "memo": "x", "lines": [line]}, headers=aud).status_code == 403
    assert client.get("/admin/users", headers=aud).status_code == 403
    me = client.get("/auth/me", headers=aud).json()
    assert me["role"]["name"] == "Auditor" and "journal.post" not in me["permissions"] and me["canManageSettings"] is False


def test_changes_are_in_the_activity_log(client, ana):  # noqa: F811 (fixtures)
    client.post("/finance/ledger/accounts", json={"code": "6150", "name": "Representation", "type": "expense"}, headers=ana)
    client.put("/tax/profile", json=REGISTRATION, headers=ana)
    log = client.get("/admin/audit", headers=ana).json()["items"]
    actions = [e["action"] for e in log]
    assert "account.created" in actions and "tax.profile_updated" in actions
    assert next(e for e in log if e["action"] == "account.created")["target"] == "6150 Representation"


def test_a_new_role_and_a_person_given_it(client, ana):  # noqa: F811 (fixtures)
    roles = client.get("/admin/roles", headers=ana).json()
    assert {r["name"] for r in roles["roles"]} == {"Administrator", "Finance Staff", "Auditor"}
    cashier = client.post("/admin/roles", json={"name": "Cashier", "description": "Releases cash only.", "permissions": ["funds.view", "funds.release"]}, headers=ana)
    assert cashier.status_code == 201, cashier.text
    made = client.post("/admin/users", json={"email": "cy@example.com", "fullName": "Cy Tan", "roleId": cashier.json()["id"], "password": "a long enough password 1"}, headers=ana)
    assert made.status_code == 201, made.text
    cy = bearer(sign_in(client, "cy@example.com", "a long enough password 1"))
    assert client.get("/finance/funds", headers=cy).status_code == 200
    assert client.get("/finance/ledger/accounts", headers=cy).status_code == 403
