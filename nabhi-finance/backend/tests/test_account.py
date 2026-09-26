"""The account page: the role, what it allows, and the sign-ins."""

from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def test_admin_and_staff_see_their_role_and_rights(client, ana, ben):
    admin = client.get("/auth/account", headers=ana).json()
    staff = client.get("/auth/account", headers=ben).json()
    assert admin["role"]["name"] == "Finance Admin" and staff["role"]["name"] == "Finance Staff"
    chart = lambda a: next(x for x in a["areas"] if x["name"] == "Chart of accounts")["actions"]  # noqa: E731
    assert chart(admin) == ["View", "Add and edit"] and chart(staff) == ["View"]
    assert staff["signedInAt"] and staff["previousSignIn"] is None
