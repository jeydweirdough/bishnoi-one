"""Staff accounts for this console: added, changed, given a new password and deleted, by a Platform Admin."""

from tests.conftest import sign_in


def staff_id(client, headers, email):
    return next(s["id"] for s in client.get("/platform/staff", headers=headers).json()["staff"] if s["email"] == email)


def test_an_admin_adds_changes_resets_and_deletes_staff(client, ana, ben):
    r = client.post("/platform/staff", json={"fullName": "Cora Diaz", "email": "Cora@Example.com", "role": "member"}, headers=ana)
    assert r.status_code == 201, r.text
    made = r.json()["password"]
    assert made and r.json()["staff"]["email"] == "cora@example.com"
    assert sign_in(client, "cora@example.com", made).status_code == 200
    cora = r.json()["staff"]["id"]
    # The same email twice is refused; Support can't add anyone.
    assert client.post("/platform/staff", json={"fullName": "Again", "email": "cora@example.com"}, headers=ana).status_code == 422
    assert client.post("/platform/staff", json={"fullName": "Nope", "email": "not an email"}, headers=ana).status_code == 422
    assert client.post("/platform/staff", json={"fullName": "Dan", "email": "dan@example.com"}, headers=ben).status_code == 403
    # Changed: name and email.
    r = client.patch(f"/platform/staff/{cora}", json={"fullName": "Cora D. Diaz", "email": "cora.diaz@example.com"}, headers=ana)
    assert r.status_code == 200 and r.json()["staff"]["fullName"] == "Cora D. Diaz"
    # A new password: the old one stops working.
    fresh = client.post(f"/platform/staff/{cora}/password", json={}, headers=ana).json()["password"]
    assert sign_in(client, "cora.diaz@example.com", made).status_code == 401
    assert sign_in(client, "cora.diaz@example.com", fresh).status_code == 200
    # Deleted: they can't sign in.
    assert client.delete(f"/platform/staff/{cora}", headers=ana).status_code == 204
    assert sign_in(client, "cora.diaz@example.com", fresh).status_code == 401


def test_the_platform_keeps_an_admin(client, ana):
    me = staff_id(client, ana, "ana@example.com")
    assert client.delete(f"/platform/staff/{me}", headers=ana).status_code == 409
    assert client.post(f"/platform/staff/{me}/password", json={}, headers=ana).status_code == 409
    # Your own name can change; your own role can't.
    assert client.patch(f"/platform/staff/{me}", json={"fullName": "Ana R."}, headers=ana).status_code == 200
    assert client.patch(f"/platform/staff/{me}", json={"role": "member"}, headers=ana).status_code == 409
    # With another Platform Admin, one of them can become Support.
    r = client.post("/platform/staff", json={"fullName": "Eve", "email": "eve@example.com", "role": "admin", "password": "another long one"}, headers=ana)
    eve = r.json()["staff"]["id"]
    assert client.patch(f"/platform/staff/{eve}", json={"role": "member"}, headers=ana).status_code == 200


def test_staff_have_one_password_their_bishnoi_one_accounts(client, ana):
    """2026-10-27: a staff password reset left the person's account password as it was."""
    from tests.conftest import make_company

    getmeds = make_company(client, ana)
    person = client.post("/platform/users", json={"companyId": getmeds["id"], "fullName": "Ai Four", "email": "ai4@getmeds.ph", "isCompanyAdmin": True}, headers=ana).json()["user"]
    assert client.post(f"/platform/users/{person['id']}/password", json={"password": "account password 1"}, headers=ana).status_code == 200

    # Made staff afterwards: no password of their own; the account's signs them in here.
    staff = client.post("/platform/staff", json={"fullName": "Ai Four", "email": "ai4@getmeds.ph", "role": "admin"}, headers=ana)
    assert staff.status_code == 201, staff.text
    assert staff.json()["password"] is None
    assert client.post("/auth/login", json={"email": "ai4@getmeds.ph", "password": "account password 1"}).status_code == 200

    # A staff reset is the account's password too.
    r = client.post(f"/platform/staff/{staff.json()['staff']['id']}/password", json={"password": "one password 2"}, headers=ana)
    assert r.status_code == 200, r.text
    assert client.post("/identity/login", json={"email": "ai4@getmeds.ph", "password": "one password 2"}).status_code == 200
    assert client.post("/auth/login", json={"email": "ai4@getmeds.ph", "password": "one password 2"}).status_code == 200
    assert client.post("/identity/login", json={"email": "ai4@getmeds.ph", "password": "account password 1"}).status_code == 401
