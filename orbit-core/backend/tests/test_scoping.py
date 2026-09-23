"""The scoping rule: (division, subdivision) is the key, pairwise, everywhere."""

import re
from pathlib import Path

import pytest

from app.scope import Scope
from app.store.local import LocalBackend
from app.store.query import Eq, Query, Search
from app.store.records import Create, Patch, Records, check_mutation
from app.tenancy import FIRST_ORG_ID

BNB_MD = Scope("bnb", "md-telesales")
BNB_GEN = Scope("bnb", "general")
B2C_MD = Scope("b2c", "md-telesales")
B2C_GEN = Scope("b2c", "general")


def doc(scope: Scope, name: str) -> dict:
    return {"_id": name, "_type": "customer", "name": name, **scope.stamp()}


@pytest.fixture
def store() -> Records:
    records = Records(LocalBackend(None)).for_org(FIRST_ORG_ID)
    records.commit([Create(doc(s, s.key)) for s in (BNB_MD, BNB_GEN, B2C_MD, B2C_GEN)])
    return records


def test_same_subdivision_in_two_divisions_is_two_scopes():
    assert BNB_MD != B2C_MD
    assert BNB_MD.key != B2C_MD.key


def test_access_is_pairwise_not_a_cross_product(store):
    """Someone on B&B/MD Telesales and B2C/General must not get B2C/MD Telesales
    or B&B/General, which separate division/subdivision filters would allow."""
    found = store.find(Query("customer", {BNB_MD, B2C_GEN}))
    assert {d["_id"] for d in found} == {"bnb/md-telesales", "b2c/general"}


def test_groq_filters_on_the_combined_key():
    text, params = Query("customer", {BNB_MD, B2C_GEN}).groq()
    assert text == "*[_type == $type && scopeKey in $scopeKeys][0...50]"
    assert params == {"type": "customer", "scopeKeys": ["b2c/general", "bnb/md-telesales"]}


def test_groq_passes_values_as_parameters():
    text, params = Query(
        "customer", {BNB_MD}, (Eq("status", '"] || true || ["'), Search(("name",), 'dr "alma')), (("sortName", "asc"),)
    ).groq()
    assert '"' not in text
    assert text == (
        "*[_type == $type && scopeKey in $scopeKeys && status == $p0 && (name match $p1_0) && (name match $p1_1)]"
        " | order(sortName asc)[0...50]"
    )
    assert params["p1_0"] == "dr*" and params["p1_1"] == "alma*"


@pytest.mark.parametrize("bad", ["name)", "a b", "x==1", "_type]|", ""])
def test_field_names_are_checked(bad):
    with pytest.raises(ValueError):
        Query("customer", {BNB_MD}, (Eq(bad, 1),)).groq()


def test_no_scopes_means_no_store_call():
    class Exploding:
        kind = "test"

        def fetch(self, query):
            raise AssertionError("should not be called")

        count = fetch

    records = Records(Exploding()).for_org(FIRST_ORG_ID)
    assert records.find(Query("customer", frozenset())) == []
    assert records.count(Query("customer", frozenset())) == 0


def test_records_with_an_inconsistent_stamp_are_dropped():
    backend = LocalBackend(None)
    bad = {**doc(BNB_MD, "forged"), "scopeKey": "b2c/general", "orgId": FIRST_ORG_ID}  # claims B2C/General, fields say B&B
    backend._docs["forged"] = bad
    assert Records(backend).for_org(FIRST_ORG_ID).find(Query("customer", {B2C_GEN})) == []


def test_writes_need_a_consistent_stamp():
    with pytest.raises(ValueError):
        check_mutation(Create({"_id": "x", "_type": "customer", "division": "bnb", "subdivision": "md-telesales"}))
    with pytest.raises(ValueError):
        check_mutation(Create({**doc(BNB_MD, "x"), "scopeKey": "md-telesales"}))
    with pytest.raises(ValueError):  # moving team without the division and key
        check_mutation(Patch("x", {"subdivision": "general"}))
    check_mutation(Patch("x", BNB_GEN.stamp()))


def test_search_matches_word_prefixes_like_groq(store):
    store.commit([Create({**doc(BNB_MD, "alma"), "name": "Dr. Alma Dizon"})])
    hit = lambda text: [d["_id"] for d in store.find(Query("customer", {BNB_MD}, (Search(("name",), text),)))]
    assert hit("alm") == ["alma"]
    assert hit("dr diz") == ["alma"]
    assert hit("lma") == []


def test_no_groq_filters_on_subdivision_outside_the_query_builder():
    """A GROQ filter on subdivision alone is the bug the project rules name.
    Reads go through Query, which filters on scopeKey; nothing else should
    write `subdivision == $...` or `subdivision in $...`."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    pattern = re.compile(r"subdivision\s*(==|in)\s*\$")
    offenders = [str(p) for p in app_dir.rglob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
