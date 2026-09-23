from dataclasses import dataclass

from app.access import resolve
from app.modules import DEFAULT_ROLES
from app.scope import Scope

MATRIX = {key: {m: set(actions) for m, actions in grants.items()} for key, _, _, grants in DEFAULT_ROLES}
TEAMS = {
    "bnb": ["general", "md-telesales"],
    "b2c": ["general", "md-telesales"],
    "hos": ["hospital", "telesales"],
    "finance": ["general"],
}


@dataclass
class A:
    role_key: str
    module_key: str
    division_code: str | None = None
    subdivision_code: str | None = None


def test_rep_gets_their_team_only_and_cannot_delete():
    access = resolve([A("rep", "bnb", "bnb", "md-telesales")], MATRIX, TEAMS)
    assert access.scopes("bnb", "view") == {Scope("bnb", "md-telesales")}
    assert not access.can("bnb", "delete")
    assert not access.can("b2c", "view")


def test_two_teams_in_two_divisions_stay_pairwise():
    access = resolve(
        [A("rep", "bnb", "bnb", "md-telesales"), A("rep", "b2c", "b2c", "general")], MATRIX, TEAMS
    )
    assert access.scopes("bnb", "view") == {Scope("bnb", "md-telesales")}
    assert access.scopes("b2c", "view") == {Scope("b2c", "general")}
    assert not access.can_in("b2c", "view", Scope("b2c", "md-telesales"))


def test_division_head_gets_every_team_in_the_division():
    access = resolve([A("division_head", "bnb", "bnb")], MATRIX, TEAMS)
    assert access.scopes("bnb", "delete") == {Scope("bnb", "general"), Scope("bnb", "md-telesales")}


def test_sales_module_never_reaches_outside_its_own_division():
    access = resolve([A("rep", "bnb", "b2c", "general")], MATRIX, TEAMS)
    assert not access.can("bnb", "view")
    access = resolve([A("rep", "bnb")], MATRIX, TEAMS)  # "all divisions" still means B&B's teams
    assert access.scopes("bnb", "view") == {Scope("bnb", "general"), Scope("bnb", "md-telesales")}


def test_unknown_team_grants_nothing():
    assert not resolve([A("rep", "bnb", "bnb", "nope")], MATRIX, TEAMS).can("bnb", "view")


def test_executive_sees_everything_and_changes_nothing():
    access = resolve([A("executive", "*")], MATRIX, TEAMS)
    assert access.scopes("hos", "view") == {Scope("hos", "hospital"), Scope("hos", "telesales")}
    assert access.can("finance", "view")
    assert not access.can("bnb", "create")
    assert not access.manage_settings


def test_department_staff_span_divisions_in_their_module_only():
    access = resolve([A("department_staff", "finance")], MATRIX, TEAMS)
    assert Scope("bnb", "md-telesales") in access.scopes("finance", "view")
    assert not access.can("bnb", "view")
    assert not access.can("hr", "view")


def test_admin_manages_settings_but_sees_no_records():
    access = resolve([A("admin", "*")], MATRIX, TEAMS)
    assert access.manage_settings
    assert not access.can("bnb", "view")


def test_settings_are_never_granted_by_a_team_scoped_assignment():
    access = resolve([A("admin", "*", "b2c", "md-telesales")], MATRIX, TEAMS)
    assert not access.manage_settings
    assert not resolve([A("admin", "*", "b2c")], MATRIX, TEAMS).manage_settings
