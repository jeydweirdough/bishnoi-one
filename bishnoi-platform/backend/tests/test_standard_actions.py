"""The standard actions (2026-11-04): one vocabulary over every app's own permissions, and what the three levels hold by default."""

from app import standard_actions as sa
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def test_an_apps_action_words_are_named_the_standard_way_and_the_rest_are_never_guessed():
    assert sa.standard_of("view") == "read" and sa.standard_of("edit") == "update" and sa.standard_of("approve") == "approve"
    assert sa.standard_of("Void") == "void" and sa.standard_of("transfer") == "transfer"
    for word in ("receive", "dispatch", "release", "verify", "roles", "users", "audit", "manage"):
        assert sa.standard_of(word) is None, word
    assert [sa.kind_of(x) for x in ("read", "submit", "post", None)] == ["crud", "workflow", "special", "other"]


def test_each_level_holds_what_the_one_below_does_and_never_delete_post_or_void():
    assert set(sa.COACHEE) < set(sa.COACH) < set(sa.MENTOR)
    for level in sa.LEVELS.values():
        assert not {"delete", "post", "void"} & set(level)
    areas = [{"key": "quotes", "actions": [
        {"key": "view", "permission": "quotes.view"}, {"key": "edit", "permission": "quotes.edit"}, {"key": "approve", "permission": "quotes.approve"},
        {"key": "delete", "permission": "quotes.delete"}, {"key": "release", "permission": "quotes.release"}]}]
    scopes = [{"key": "own"}, {"key": "team"}, {"key": "managed"}, {"key": "all"}]
    assert sa.defaults(areas, scopes, "coachee") == (["quotes.edit", "quotes.view"], "own")
    assert sa.defaults(areas, scopes, "coach") == (["quotes.approve", "quotes.edit", "quotes.view"], "managed")
    # A module with fewer scopes gets the nearest one it has; an unscoped module gets none.
    assert sa.defaults(areas, [{"key": "own"}, {"key": "all"}], "mentor")[1] == "own"
    assert sa.defaults(areas, [], "mentor")[1] is None


def test_the_roles_screen_gets_standard_names_and_the_defaults_for_the_companys_apps(client, getmeds):
    h = getmeds["owner"]["h"]
    crm = next(m for m in client.get("/identity/access", headers=h).json()["modules"] if m["key"] == "crm")
    assert [(a["key"], a["standard"], a["kind"]) for a in crm["areas"][0]["actions"]] == [("view", "read", "crud"), ("edit", "update", "crud")]
    coach = client.get("/identity/access/standard/coach", headers=h).json()
    assert coach["permissions"]["crm"] == ["customers.edit", "customers.view"] and coach["scopes"]["crm"] == "team"
    assert coach["permissions"]["pharmacy"] == ["prescriptions.view"] and "pharmacy" not in coach["scopes"]
    assert client.get("/identity/access/standard/boss", headers=h).status_code == 404
    assert client.get("/identity/access/standard/coach", headers=getmeds["jade"]["h"]).status_code == 403
