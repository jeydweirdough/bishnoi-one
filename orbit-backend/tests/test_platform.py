"""Taking a company on: the job the Developer Admin tier exists for.

A company wants to use Orbit. A Developer Admin puts it on the platform, names
the person who will run it, and from that moment the company runs itself: its
Admin sets its divisions, its prices, its people. Nobody from Orbit needs to be
in it, and nobody in it can see any other.
"""

from tests.conftest import DEMO_PASSWORD


def signed_in(client, email: str, password: str = DEMO_PASSWORD) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def a_company(**over) -> dict:
    return {
        "name": "Northwind Pharma",
        "adminEmail": "ada@northwind.test",
        "adminName": "Ada Lim",
        "adminPassword": "northwind12345",
        **over,
    }


def add(client, headers, **over):
    return client.post("/platform/companies", json=a_company(**over), headers=headers)


def slugs(client, headers) -> list[str]:
    return [c["slug"] for c in client.get("/platform/companies", headers=headers).json()["companies"]]


# --- who may do it ---------------------------------------------------------------


def test_only_a_developer_admin_reaches_the_platform(client, as_):
    for who in ("carmen", "ramon", "lorna"):
        assert client.get("/platform/companies", headers=as_(who)).status_code == 403, who
        assert add(client, as_(who)).status_code == 403, who


def test_a_developer_admin_sees_the_companies(client, as_):
    assert slugs(client, as_("jun")) == ["getmeds"]


# --- taking one on ---------------------------------------------------------------


def test_a_company_joins_and_opens_to_a_working_system(client, as_):
    jun = as_("jun")
    made = add(client, jun)
    assert made.status_code == 201, made.text
    company = made.json()["company"]

    assert company["name"] == "Northwind Pharma"
    assert company["slug"] == "northwind-pharma"  # made from the name
    assert company["status"] == "active"
    assert company["peopleCount"] == 1 and company["isReady"] is True
    assert slugs(client, jun) == ["getmeds", "northwind-pharma"]

    # Seeded, not blank: it has the divisions, teams, roles and apps to start from.
    there = {"Authorization": f"Bearer {client.post('/auth/switch-org', json={'orgId': company['id']}, headers=jun).json()['accessToken']}"}
    roles = client.get("/admin/roles", headers=there).json()
    assert [r["key"] for r in roles["roles"]][-1] == "admin"
    assert len(roles["modules"]) > 10
    assert [a["name"] for a in client.get("/admin/apps", headers=there).json()["apps"]] == ["Orders"]


def test_its_admin_runs_it_from_the_first_sign_in(client, as_):
    add(client, as_("jun"))
    ada = signed_in(client, "ada@northwind.test", "northwind12345")
    body = client.get("/auth/me", headers=ada).json()

    assert body["org"]["name"] == "Northwind Pharma"
    assert body["canManageSettings"] is True
    assert body["isDeveloperAdmin"] is False
    # they run their own company and know of no other
    assert [o["slug"] for o in client.get("/auth/orgs", headers=ada).json()["items"]] == ["northwind-pharma"]
    assert client.get("/platform/companies", headers=ada).status_code == 403
    assert client.get("/admin/lists", headers=ada).status_code == 200


def test_the_new_company_sees_nothing_of_the_old_one(client, as_):
    add(client, as_("jun"))
    ada = signed_in(client, "ada@northwind.test", "northwind12345")
    theirs = {u["email"] for u in client.get("/admin/users", headers=ada).json()}
    assert theirs == {"ada@northwind.test"}
    assert client.get("/sales/customers", params={"division": "bnb"}, headers=ada).status_code in (200, 403)


def test_what_it_is_called_is_its_own_to_set(client, as_):
    made = add(
        client, as_("jun"),
        name="Sunrise Distribution", slug="sunrise", brandName="Sunrise",
        currency="USD", minorUnits=2, timezone="America/New_York", orderPrefix="SUN",
    )
    assert made.status_code == 201, made.text
    company = made.json()["company"]
    assert (company["slug"], company["currency"], company["timezone"], company["orderPrefix"]) == (
        "sunrise", "USD", "America/New_York", "SUN"
    )


def test_two_companies_cannot_share_an_address(client, as_):
    jun = as_("jun")
    assert add(client, jun).status_code == 201
    again = add(client, jun, adminEmail="someone@else.test")
    assert again.status_code == 409
    assert "already a company" in again.json()["detail"]


def test_somebody_already_on_orbit_joins_with_the_password_they_have(client, as_):
    """Ada runs one company and is asked to run another. She does not get a
    second account, and the password typed here is not used."""
    jun = as_("jun")
    assert add(client, jun).status_code == 201
    second = add(client, jun, name="Southwind", adminPassword="ignored12345")
    assert second.status_code == 201
    assert second.json()["admin"]["joinedExistingAccount"] is True

    ada = signed_in(client, "ada@northwind.test", "northwind12345")
    assert {o["slug"] for o in client.get("/auth/orgs", headers=ada).json()["items"]} == {"northwind-pharma", "southwind"}


def test_a_company_can_be_switched_off_and_back_on(client, as_):
    jun = as_("jun")
    company = add(client, jun).json()["company"]
    off = client.patch(f"/platform/companies/{company['id']}", params={"on": False}, headers=jun)
    assert off.status_code == 200 and off.json()["company"]["status"] == "suspended"
    # nobody in it can sign in, and nothing of theirs is gone
    assert client.post("/auth/login", json={"email": "ada@northwind.test", "password": "northwind12345"}).status_code == 403
    on = client.patch(f"/platform/companies/{company['id']}", params={"on": True}, headers=jun)
    assert on.status_code == 200 and on.json()["company"]["status"] == "active"
    assert client.post("/auth/login", json={"email": "ada@northwind.test", "password": "northwind12345"}).status_code == 200


def test_a_company_needs_a_name_worth_having(client, as_):
    jun = as_("jun")
    assert add(client, jun, name="!!!").status_code == 422
    assert add(client, jun, adminPassword="short").status_code == 422
    assert add(client, jun, adminEmail="not-an-email").status_code == 422


# --- looking through somebody's eyes ---------------------------------------------


def a_company_with_people(client, jun) -> tuple[str, list[dict]]:
    """Getmeds, whose demo people cover every division and department."""
    org = next(c["id"] for c in client.get("/platform/companies", headers=jun).json()["companies"] if c["slug"] == "getmeds")
    people = client.get(f"/platform/companies/{org}/people", headers=jun).json()["people"]
    return org, people


def view_as(client, jun, org_id: str, user_id: str):
    return client.post("/auth/view-as", json={"orgId": org_id, "userId": user_id}, headers=jun)


def test_a_companys_people_are_listed_with_who_runs_it(client, as_):
    jun = as_("jun")
    _, people = a_company_with_people(client, jun)
    assert people[0]["email"] == "carmen@pharmacrm.test"  # the owner, first
    assert people[0]["isOwner"] is True and people[0]["isAdmin"] is True
    # and a Developer Admin is in nobody's company, so not in the list
    assert "jun@pharmacrm.test" not in {p["email"] for p in people}


def test_only_a_developer_admin_may_look_through_somebody(client, as_):
    jun = as_("jun")
    org, people = a_company_with_people(client, jun)
    ana = next(p["id"] for p in people if p["email"] == "ana@pharmacrm.test")
    assert client.post("/auth/view-as", json={"orgId": org, "userId": ana}, headers=as_("carmen")).status_code == 403


def test_it_shows_exactly_what_that_person_sees(client, as_):
    """The point of it: a rep's screens depend on their teams and their records,
    and the only honest way to check them is to look."""
    jun = as_("jun")
    org, people = a_company_with_people(client, jun)
    ana = next(p["id"] for p in people if p["email"] == "ana@pharmacrm.test")

    seeing = view_as(client, jun, org, ana)
    assert seeing.status_code == 200, seeing.text
    eyes = {"Authorization": f"Bearer {seeing.json()['accessToken']}"}

    body = client.get("/auth/me", headers=eyes).json()
    assert body["user"]["email"] == "ana@pharmacrm.test"
    assert body["viewedBy"]["email"] == "jun@pharmacrm.test"
    assert body["org"]["slug"] == "getmeds"
    # her two divisions, not everything in the company
    assert {m["key"] for m in body["modules"] if m["kind"] == "sales"} == {"bnb", "b2c"}
    hers = client.get("/sales/customers", params={"division": "bnb"}, headers=eyes)
    assert hers.status_code == 200
    assert client.get("/admin/users", headers=eyes).status_code == 403  # she is no admin


def test_nothing_can_be_changed_while_looking(client, as_):
    """A change made this way would be signed with her name."""
    jun = as_("jun")
    org, people = a_company_with_people(client, jun)
    ana = next(p["id"] for p in people if p["email"] == "ana@pharmacrm.test")
    eyes = {"Authorization": f"Bearer {view_as(client, jun, org, ana).json()['accessToken']}"}

    made = client.post(
        "/sales/customers",
        json={"division": "bnb", "team": "md-telesales", "name": "Not Really Hers", "kind": "doctor"},
        headers=eyes,
    )
    assert made.status_code == 403
    assert "seeing Orbit as someone else" in made.json()["detail"]


def test_a_developer_admin_is_nobody_to_look_through(client, as_, acme):
    jun = as_("jun")
    org, _ = a_company_with_people(client, jun)
    # jun himself is in no company, so he is not even findable there
    me_id = client.get("/auth/me", headers=jun).json()["user"]["id"]
    assert view_as(client, jun, org, me_id).status_code == 404


def test_looking_is_written_down(client, as_):
    jun = as_("jun")
    org, people = a_company_with_people(client, jun)
    ana = next(p["id"] for p in people if p["email"] == "ana@pharmacrm.test")
    view_as(client, jun, org, ana)

    entries = client.get("/admin/audit", headers=as_("carmen")).json()["items"]
    looked = [e for e in entries if e["action"] == "viewed.as"]
    assert looked and looked[0]["actor"] == "jun@pharmacrm.test"
    assert "ana@pharmacrm.test" in looked[0]["target"]


def test_leaving_comes_back_as_themselves(client, as_):
    jun = as_("jun")
    org, people = a_company_with_people(client, jun)
    ana = next(p["id"] for p in people if p["email"] == "ana@pharmacrm.test")
    eyes = {"Authorization": f"Bearer {view_as(client, jun, org, ana).json()['accessToken']}"}

    back = client.post("/auth/leave", headers=eyes)
    assert back.status_code == 200
    platform = {"Authorization": f"Bearer {back.json()['accessToken']}"}
    body = client.get("/auth/me", headers=platform).json()
    assert body["user"]["email"] == "jun@pharmacrm.test"
    assert body["org"] is None and body["viewedBy"] is None
    # and the borrowed session is over
    assert client.get("/auth/me", headers=eyes).status_code == 401


def test_leaving_a_company_opened_as_themselves_also_works(client, as_):
    jun = as_("jun")
    org, _ = a_company_with_people(client, jun)
    inside = {"Authorization": f"Bearer {client.post('/auth/switch-org', json={'orgId': org}, headers=jun).json()['accessToken']}"}
    back = client.post("/auth/leave", headers=inside)
    assert back.status_code == 200
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {back.json()['accessToken']}"}).json()["org"] is None
