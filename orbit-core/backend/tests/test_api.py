from datetime import date, timedelta

from tests.conftest import names


def customer_id(client, headers, module: str, name: str) -> str:
    items = client.get("/sales/customers", params={"division": module, "q": name, "limit": 100}, headers=headers).json()["items"]
    return next(c["id"] for c in items if c["name"] == name)


# --- sign-in ---------------------------------------------------------------------------


def test_sign_in_and_me(client, as_):
    me = client.get("/auth/me", headers=as_("ana")).json()
    assert me["user"]["fullName"] == "Ana Reyes"
    assert not me["canManageSettings"]
    modules = {m["key"]: m for m in me["modules"]}
    # Her two sales teams, and Orders: a rep raises orders where she sells.
    assert set(modules) == {"bnb", "b2c", "orders"}
    assert [t["code"] for t in modules["bnb"]["teams"]] == ["md-telesales"]
    assert [t["code"] for t in modules["b2c"]["teams"]] == ["general"]
    assert modules["orders"]["kind"] == "app" and modules["orders"]["actions"] == ["view", "raise"]
    assert modules["orders"]["url"] is None  # no Orders app configured


def test_wrong_password_then_throttled(client):
    for _ in range(5):
        r = client.post("/auth/login", json={"email": "ana@pharmacrm.test", "password": "nope-nope"})
        assert r.status_code == 401
    r = client.post("/auth/login", json={"email": "ana@pharmacrm.test", "password": "demo1234"})
    assert r.status_code == 429


def test_unknown_email_looks_like_a_wrong_password(client):
    r = client.post("/auth/login", json={"email": "nobody@pharmacrm.test", "password": "whatever1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "That email and password don't match."


def test_requests_need_a_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_switching_someone_off_ends_their_session_at_once(client, as_):
    ana = as_("ana")
    ana_id = client.get("/auth/me", headers=ana).json()["user"]["id"]
    r = client.patch(f"/admin/users/{ana_id}", json={"isActive": False}, headers=as_("carmen"))
    assert r.status_code == 200
    assert client.get("/auth/me", headers=ana).status_code == 401


# --- the scoping rule, end to end ---------------------------------------------------------


B2C_FOR_ANA = {"Maria Lopez", "Jose Ramos"}
BNB_FOR_ANA = {"Dr. Alma Dizon", "Dr. Victor Salcedo", "Dr. Irene Galang", "Sta. Lucia Drugstore"}


def test_rep_on_two_teams_sees_exactly_those_two(client, as_):
    ana = as_("ana")
    assert names(client.get("/sales/customers?division=b2c", headers=ana).json()["items"]) == B2C_FOR_ANA
    assert names(client.get("/sales/customers?division=bnb", headers=ana).json()["items"]) == BNB_FOR_ANA


def test_the_list_merges_every_division_a_person_sells_in(client, as_):
    """Ana's Customers is one list, not one per division: the division is
    something a customer carries, not a place she has to go to first."""
    ana = as_("ana")
    items = client.get("/sales/customers", headers=ana).json()["items"]
    assert names(items) == B2C_FOR_ANA | BNB_FOR_ANA
    # And each row says which division it is in, because the name alone no
    # longer tells you.
    where = {i["name"]: (i["division"], i["divisionName"]) for i in items}
    assert where["Maria Lopez"] == ("b2c", "B2C")
    assert where["Dr. Alma Dizon"] == ("bnb", "B&B")


def test_merging_the_list_does_not_merge_what_you_may_see(client, as_):
    """The whole risk of one list: it must hold exactly what the per-division
    lists held together, and not one record more."""
    ana, ben, lorna = as_("ana"), as_("ben"), as_("lorna")
    everything = names(client.get("/sales/customers", headers=ana).json()["items"])
    assert everything == B2C_FOR_ANA | BNB_FOR_ANA
    # Ben's B2C customers are in a team Ana isn't on; merging must not reach them.
    assert "Dr. Cora Aquino" in names(client.get("/sales/customers", headers=ben).json()["items"])
    assert "Dr. Cora Aquino" not in everything
    # Lorna heads B&B only: her list is B&B's, and asking for B2C gets nothing
    # rather than someone else's customers.
    assert names(client.get("/sales/customers?division=b2c", headers=lorna).json()["items"]) == set()
    assert client.get("/sales/customers", headers=lorna).json()["total"] > 0


def test_out_of_scope_record_is_not_found_not_forbidden(client, as_):
    cora = customer_id(client, as_("ben"), "b2c", "Dr. Cora Aquino")
    r = client.get(f"/sales/customers/{cora}", headers=as_("ana"))
    assert r.status_code == 404


def test_a_customer_opens_wherever_you_are(client, as_):
    """A customer is reached by who it is, not by which division you thought to
    look in first: Ana sells in B&B, so Alma opens."""
    ana = as_("ana")
    alma = customer_id(client, ana, "bnb", "Dr. Alma Dizon")
    r = client.get(f"/sales/customers/{alma}", headers=ana)
    assert r.status_code == 200 and r.json()["divisionName"] == "B&B"


def test_team_filter_cannot_widen_access(client, as_):
    r = client.get("/sales/customers", params={"division": "b2c", "team": "md-telesales"}, headers=as_("ana"))
    assert r.json()["items"] == []


def test_cannot_create_in_a_team_you_are_not_on(client, as_):
    body = {"team": "md-telesales", "name": "Dr. New Person", "kind": "doctor"}
    assert client.post("/sales/customers", json={"division": "b2c", **body}, headers=as_("ana")).status_code == 403
    body["team"] = "general"
    r = client.post("/sales/customers", json={"division": "b2c", **body}, headers=as_("ana"))
    assert r.status_code == 201
    assert r.json()["teamName"] == "General"
    assert r.json()["owner"]["name"] == "Ana Reyes"


def test_division_head_sees_all_teams_in_division(client, as_):
    lorna = names(client.get("/sales/customers?division=bnb", headers=as_("lorna")).json()["items"])
    assert {"Mercado Family Clinic", "Dr. Alma Dizon"} <= lorna


def test_someone_who_sells_nowhere_has_no_sales_workspace(client, as_):
    """Joy is Finance. There is no division to ask for and nothing to merge, so
    the workspace refuses her outright rather than handing back an empty list."""
    assert client.get("/sales/customers", headers=as_("joy")).status_code == 403
    assert client.get("/sales/customers?division=bnb", headers=as_("joy")).status_code == 403


def test_executive_reads_but_cannot_write(client, as_):
    ramon = as_("ramon")
    assert client.get("/sales/customers?division=hos", headers=ramon).json()["total"] == 2
    body = {"team": "hospital", "name": "Another Hospital", "kind": "hospital"}
    assert client.post("/sales/customers", json={"division": "hos", **body}, headers=ramon).status_code == 403


# --- customers ----------------------------------------------------------------------------


def test_duplicates_are_caught_within_what_you_can_see(client, as_):
    ana = as_("ana")
    body = {"team": "md-telesales", "name": "Alma Dizon MD", "kind": "doctor", "phone": "(0917) 555-0101"}
    r = client.post("/sales/customers", json={"division": "bnb", **body}, headers=ana)
    assert r.status_code == 409
    assert [d["name"] for d in r.json()["detail"]["duplicates"]] == ["Dr. Alma Dizon"]
    assert client.post("/sales/customers", json={"division": "bnb", **body, "allowDuplicate": True}, headers=ana).status_code == 201


def test_duplicate_check_does_not_reveal_other_teams(client, as_):
    # Dr. Cora Aquino (B2C/MD Telesales) has this number; Ana can't see her team.
    body = {"team": "general", "name": "Cora A.", "kind": "patient", "phone": "0917 555 0131"}
    assert client.post("/sales/customers", json={"division": "b2c", **body}, headers=as_("ana")).status_code == 201


def test_moving_a_customer_moves_its_history(client, as_):
    lorna, ana = as_("lorna"), as_("ana")
    alma = customer_id(client, ana, "bnb", "Dr. Alma Dizon")
    before = client.get(f"/sales/customers/{alma}", headers=lorna).json()
    assert before["activities"] and before["followUps"]

    r = client.patch(f"/sales/customers/{alma}", json={"team": "general", "rev": before["rev"]}, headers=lorna)
    assert r.status_code == 200 and r.json()["team"] == "general"

    after = client.get(f"/sales/customers/{alma}", headers=lorna).json()
    assert len(after["activities"]) == len(before["activities"])
    assert {a["team"] for a in after["activities"]} == {"general"}
    assert client.get(f"/sales/customers/{alma}", headers=ana).status_code == 404
    mine = client.get("/sales/follow-ups?division=bnb", headers=ana).json()["items"]
    assert "Dr. Alma Dizon" not in {f["customerName"] for f in mine}


def test_team_lead_cannot_move_a_customer_out_of_their_team(client, as_):
    paolo = as_("paolo")
    irene = customer_id(client, paolo, "bnb", "Dr. Irene Galang")
    r = client.patch(f"/sales/customers/{irene}", json={"team": "general"}, headers=paolo)
    assert r.status_code == 403


def test_stale_edit_is_refused(client, as_):
    ana = as_("ana")
    alma = customer_id(client, ana, "bnb", "Dr. Alma Dizon")
    rev = client.get(f"/sales/customers/{alma}", headers=ana).json()["rev"]
    assert client.patch(f"/sales/customers/{alma}", json={"city": "Manila", "rev": rev}, headers=ana).status_code == 200
    r = client.patch(f"/sales/customers/{alma}", json={"city": "Pasig", "rev": rev}, headers=ana)
    assert r.status_code == 409


def test_clearing_a_field_and_required_fields(client, as_):
    ana = as_("ana")
    alma = customer_id(client, ana, "bnb", "Dr. Alma Dizon")
    r = client.patch(f"/sales/customers/{alma}", json={"specialty": ""}, headers=ana)
    assert r.status_code == 200 and r.json()["specialty"] is None
    assert client.patch(f"/sales/customers/{alma}", json={"name": ""}, headers=ana).status_code == 422


def test_rep_cannot_delete_team_lead_can_and_history_goes_too(client, as_, records):
    irene = customer_id(client, as_("ana"), "bnb", "Dr. Irene Galang")
    assert client.delete(f"/sales/customers/{irene}", headers=as_("ana")).status_code == 403
    assert client.delete(f"/sales/customers/{irene}", headers=as_("paolo")).status_code == 204
    leftovers = [d for d in records.backend._docs.values() if d.get("customerId") == irene]
    assert leftovers == []


def test_headquarters_must_belong_to_the_team(client, as_):
    lorna = as_("lorna")
    body = {"team": "md-telesales", "name": "Somewhere Clinic", "kind": "clinic", "headquarters": "cebu"}
    assert client.post("/sales/customers", json={"division": "bnb", **body}, headers=lorna).status_code == 422
    body["team"] = "general"
    r = client.post("/sales/customers", json={"division": "bnb", **body}, headers=lorna)
    assert r.status_code == 201 and r.json()["headquartersName"] == "CEBU"


def test_search(client, as_):
    r = client.get("/sales/customers", params={"division": "bnb", "q": "salc"}, headers=as_("ana")).json()
    assert names(r["items"]) == {"Dr. Victor Salcedo"}
    r = client.get("/sales/customers", params={"division": "bnb", "q": "0917555010"}, headers=as_("ana")).json()
    assert r["total"] == 4


# --- activities and follow-ups -------------------------------------------------------------


def test_logging_a_call_with_a_follow_up(client, as_):
    ana = as_("ana")
    victor = customer_id(client, ana, "bnb", "Dr. Victor Salcedo")
    due = (date.today() + timedelta(days=2)).isoformat()
    body = {"kind": "call", "outcome": "reached", "summary": "Agreed to a demo.", "followUp": {"title": "Demo", "dueOn": due}}
    r = client.post(f"/sales/customers/{victor}/activities", json=body, headers=ana)
    assert r.status_code == 201
    detail = client.get(f"/sales/customers/{victor}", headers=ana).json()
    assert detail["activities"][0]["summary"] == "Agreed to a demo."
    assert detail["lastContactAt"] == detail["activities"][0]["occurredAt"]
    assert any(f["title"] == "Demo" and f["assignee"]["name"] == "Ana Reyes" for f in detail["followUps"])


def test_follow_up_can_only_go_to_someone_who_can_see_the_team(client, as_):
    ana = as_("ana")
    victor = customer_id(client, ana, "bnb", "Dr. Victor Salcedo")
    people = client.get("/sales/people", params={"division": "bnb", "team": "md-telesales"}, headers=ana).json()
    # Her own team, its lead, the division head, and the two who see every
    # division: the Executive (read-only) and Management (approves its orders).
    assert {p["name"] for p in people} == {
        "Ana Reyes", "Paolo Mendoza", "Lorna Bautista", "Ramon Santos", "Mila Aguilar"
    }
    ben_id = client.get("/auth/me", headers=as_("ben")).json()["user"]["id"]
    body = {"title": "Hand over", "dueOn": date.today().isoformat(), "assigneeId": ben_id}
    assert client.post(f"/sales/customers/{victor}/follow-ups", json=body, headers=ana).status_code == 422


def test_complete_and_reopen_a_follow_up(client, as_):
    ana = as_("ana")
    items = client.get("/sales/follow-ups?division=bnb", headers=ana).json()["items"]
    target = next(f for f in items if f["title"] == "Call back after 3pm")
    assert target["bucket"] == "overdue"
    done = client.patch(f"/sales/follow-ups/{target['id']}", json={"status": "done"}, headers=ana).json()
    assert done["status"] == "done" and done["doneBy"]["name"] == "Ana Reyes"
    again = client.patch(f"/sales/follow-ups/{target['id']}", json={"status": "open"}, headers=ana).json()
    assert again["status"] == "open" and again["doneBy"] is None


def test_home_follow_ups_cover_every_workspace_but_only_mine(client, as_):
    items = client.get("/me/follow-ups", headers=as_("ana")).json()["items"]
    assert {i["module"] for i in items} == {"bnb", "b2c"}
    assert "Dr. Cora Aquino" not in {i["customerName"] for i in items}


def test_summary_counts(client, as_):
    ana = as_("ana")
    one = client.get("/sales/summary", params={"division": "bnb"}, headers=ana).json()
    assert one["counts"]["customers"] == 4
    assert one["counts"]["overdue"] == 1 and one["counts"]["dueToday"] == 1
    assert all(a["customerName"] for a in one["recentActivity"])

    # Without a division it is the overview of everything she sells: B&B's four
    # and B2C's two, counted once.
    both = client.get("/sales/summary", headers=ana).json()
    assert both["counts"]["customers"] == 6


def test_malformed_team_is_a_clear_error(client, as_):
    for path in ("/sales/customers", "/sales/follow-ups", "/sales/people"):
        r = client.get(path, params={"division": "bnb", "team": "Bad!"}, headers=as_("ana"))
        assert r.status_code == 422, path


def test_editing_from_a_copy_older_than_a_logged_call_is_refused(client, as_):
    ana = as_("ana")
    alma = customer_id(client, ana, "bnb", "Dr. Alma Dizon")
    rev = client.get(f"/sales/customers/{alma}", headers=ana).json()["rev"]
    body = {"kind": "note", "summary": "Moved clinics."}
    assert client.post(f"/sales/customers/{alma}/activities", json=body, headers=ana).status_code == 201
    r = client.patch(f"/sales/customers/{alma}", json={"team": "general", "rev": rev}, headers=as_("lorna"))
    assert r.status_code == 409
