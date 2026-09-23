"""Bulk actions and the job queue behind them: every record checked on its own,
what couldn't be done reported by id, big jobs queued and worked in batches."""

import time

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.jobs import JobQueue
from app.models import Profile
from app.ratelimit import kind_of
from app.routers.bulk import CHANGED, MISSING, NOT_ALLOWED, SWITCHED_OFF, as_person, commit_items, repriced
from app.scope import Scope
from app.store.query import Query
from app.store.local import LocalBackend
from app.store.records import Create, Patch, Records
from app.store.sanity import SanityBackend
from app.tenancy import FIRST_ORG_ID
from tests.conftest import build_app, customer_id, product_ids
from tests.test_finance import discount_quote


def open_follow_ups(client, headers, module: str) -> dict[str, dict]:
    r = client.get("/sales/follow-ups", params={"division": module, "who": "me"}, headers=headers)
    assert r.status_code == 200, r.text
    return {f["customerName"]: f for f in r.json()["items"]}


def failures(job: dict) -> dict[str, str]:
    return {f["id"]: f["error"] for f in job["failures"]}


# --- follow-ups ----------------------------------------------------------------------


def test_marking_follow_ups_done_together(client, as_):
    ana = as_("ana")
    mine = open_follow_ups(client, ana, "bnb")
    ids = [f["id"] for f in mine.values()]
    assert len(ids) == 2

    r = client.post("/sales/bulk/follow-ups", json={"action": "done", "ids": ids}, headers=ana)
    assert r.status_code == 202, r.text
    job = r.json()
    # Small enough for one batch, so it's done by the time the answer comes back.
    assert (job["status"], job["total"], job["succeeded"], job["failed"]) == ("done", 2, 2, 0)
    assert open_follow_ups(client, ana, "bnb") == {}

    done = client.get("/sales/follow-ups", params={"division": "bnb", "state": "done"}, headers=ana).json()["items"]
    assert {f["id"] for f in done} >= set(ids)
    assert all(f["doneBy"]["name"] == "Ana Reyes" for f in done if f["id"] in ids)


def test_what_couldnt_be_done_is_named_not_skipped(client, as_):
    ana = as_("ana")
    mine = open_follow_ups(client, ana, "b2c")
    bens = open_follow_ups(client, as_("ben"), "b2c")["Dr. Cora Aquino"]["id"]  # a team Ana can't see
    ids = [mine["Maria Lopez"]["id"], bens, "no-such-id"]

    job = client.post("/sales/bulk/follow-ups", json={"action": "done", "ids": ids}, headers=ana).json()
    assert (job["succeeded"], job["failed"]) == (1, 2)
    assert failures(job) == {bens: MISSING, "no-such-id": MISSING}
    assert open_follow_ups(client, as_("ben"), "b2c")["Dr. Cora Aquino"]["status"] == "open"


def test_moving_and_reassigning_follow_ups(client, as_):
    paolo = as_("paolo")
    team = client.get("/sales/follow-ups", params={"division": "bnb", "who": "team"}, headers=paolo).json()["items"]
    ids = [f["id"] for f in team]

    r = client.post("/sales/bulk/follow-ups", json={"action": "due", "ids": ids}, headers=paolo)
    assert r.status_code == 422  # which date?
    job = client.post("/sales/bulk/follow-ups", json={"action": "due", "ids": ids, "dueOn": "2026-10-01"}, headers=paolo).json()
    assert job["failed"] == 0
    assert {f["dueOn"] for f in client.get("/sales/follow-ups", params={"division": "bnb", "who": "team"}, headers=paolo).json()["items"]} == {"2026-10-01"}

    lorna_id = client.get("/sales/people", params={"division": "bnb", "team": "md-telesales"}, headers=paolo).json()
    lorna_id = next(p["id"] for p in lorna_id if p["name"] == "Lorna Bautista")
    job = client.post("/sales/bulk/follow-ups", json={"action": "assign", "ids": ids, "assigneeId": lorna_id}, headers=paolo).json()
    assert job["failed"] == 0
    assert open_follow_ups(client, as_("lorna"), "bnb").keys() == {"Dr. Alma Dizon", "Dr. Victor Salcedo", "Dr. Irene Galang"}

    # Someone who can't see B&B at all is refused before anything is queued.
    ben_id = next(p["id"] for p in client.get("/sales/people", params={"division": "b2c", "team": "md-telesales"}, headers=as_("ben")).json())
    r = client.post("/sales/bulk/follow-ups", json={"action": "assign", "ids": ids, "assigneeId": ben_id}, headers=paolo)
    assert r.status_code == 422


# --- customers -----------------------------------------------------------------------


def test_changing_status_and_owner_of_customers(client, as_):
    paolo = as_("paolo")
    alma, victor = (customer_id(client, paolo, "bnb", n) for n in ("Dr. Alma Dizon", "Dr. Victor Salcedo"))

    job = client.post("/sales/bulk/customers", json={"action": "status", "ids": [alma, victor], "status": "inactive"}, headers=paolo).json()
    assert job["succeeded"] == 2
    assert {c["status"] for c in client.get("/sales/customers", params={"division": "bnb", "status": "inactive"}, headers=paolo).json()["items"]} == {"inactive"}

    people = client.get("/sales/people", params={"division": "bnb", "team": "md-telesales"}, headers=paolo).json()
    paolo_id = next(p["id"] for p in people if p["name"] == "Paolo Mendoza")
    job = client.post("/sales/bulk/customers", json={"action": "owner", "ids": [alma, victor], "ownerId": paolo_id}, headers=paolo).json()
    assert job["succeeded"] == 2
    assert client.get(f"/sales/customers/{alma}", headers=paolo).json()["owner"]["name"] == "Paolo Mendoza"


def test_a_follow_up_for_each_customer(client, as_):
    """The retention page's win-back round: one call each for the customers going quiet."""
    ana = as_("ana")
    ids = [customer_id(client, ana, "b2c", n) for n in ("Maria Lopez", "Jose Ramos")]
    body = {"action": "follow_up", "ids": ids, "followUp": {"title": "Win-back call", "dueOn": "2026-09-20"}}
    job = client.post("/sales/bulk/customers", json=body, headers=ana).json()
    assert job["succeeded"] == 2
    for cid in ids:
        titles = [f["title"] for f in client.get(f"/sales/customers/{cid}", headers=ana).json()["followUps"]]
        assert "Win-back call" in titles


def test_a_leads_win_back_round_goes_to_each_owner(client, as_):
    paolo = as_("paolo")
    ids = [customer_id(client, paolo, "bnb", n) for n in ("Dr. Alma Dizon", "Dr. Irene Galang")]  # Ana's, Paolo's
    body = {"action": "follow_up", "ids": ids, "toOwner": True, "followUp": {"title": "Win back", "dueOn": "2026-09-20"}}
    assert client.post("/sales/bulk/customers", json=body, headers=paolo).json()["succeeded"] == 2
    for who, customer in (("ana", "Dr. Alma Dizon"), ("paolo", "Dr. Irene Galang")):
        items = client.get("/sales/follow-ups", params={"division": "bnb", "who": "me"}, headers=as_(who)).json()["items"]
        assert [f["customerName"] for f in items if f["title"] == "Win back"] == [customer]


def test_deleting_customers_takes_their_records_along(client, as_):
    ana, paolo = as_("ana"), as_("paolo")
    alma = customer_id(client, paolo, "bnb", "Dr. Alma Dizon")
    # Reps don't delete.
    assert client.post("/sales/bulk/customers", json={"action": "delete", "ids": [alma]}, headers=ana).status_code == 403

    job = client.post("/sales/bulk/customers", json={"action": "delete", "ids": [alma]}, headers=paolo).json()
    assert job["succeeded"] == 1
    assert client.get(f"/sales/customers/{alma}", headers=paolo).status_code == 404
    assert "Dr. Alma Dizon" not in open_follow_ups(client, ana, "bnb")


def test_bulk_is_capped_and_needs_something_to_do(client, as_):
    ana = as_("ana")
    assert client.post("/sales/bulk/customers", json={"action": "status", "ids": [], "status": "active"}, headers=ana).status_code == 422
    too_many = [f"id-{n}" for n in range(501)]
    r = client.post("/sales/bulk/customers", json={"action": "status", "ids": too_many, "status": "active"}, headers=ana)
    assert r.status_code == 422
    r = client.post("/sales/bulk/customers", json={"action": "shout", "ids": ["x"]}, headers=ana)
    assert r.status_code == 422


# --- finance and inventory -------------------------------------------------------------


def test_finance_approves_several_quotes_at_once(client, as_):
    q = discount_quote(client, as_)
    joy, ramon = as_("joy"), as_("ramon")
    assert client.post("/finance/bulk/approvals", json={"ids": [q["id"]], "decision": "reject"}, headers=joy).status_code == 422
    assert client.post("/finance/bulk/approvals", json={"ids": [q["id"]], "decision": "approve"}, headers=ramon).status_code == 403

    job = client.post("/finance/bulk/approvals", json={"ids": [q["id"]], "decision": "approve", "note": "Q4 deal"}, headers=joy).json()
    assert job["succeeded"] == 1
    assert client.get(f"/finance/quotes/{q['id']}", headers=joy).json()["approval"]["status"] == "approved"

    again = client.post("/finance/bulk/approvals", json={"ids": [q["id"]], "decision": "approve"}, headers=joy).json()
    assert failures(again) == {q["id"]: "It isn't waiting for approval any more."}


def test_repricing_and_switching_off_products(client, as_):
    iris = as_("iris")
    ids = product_ids(client, as_("ana"), "b2c")
    chosen = [ids["ASC-500"], ids["PARA-SYR"]]
    before = {p["id"]: p["prices"] for p in client.get("/inventory/products", headers=iris).json()}

    body = {"action": "reprice", "ids": chosen, "changeBp": 1000, "priceType": "srp"}
    job = client.post("/inventory/bulk/products", json=body, headers=iris).json()
    assert job["succeeded"] == 2
    after = {p["id"]: p["prices"] for p in client.get("/inventory/products", headers=iris).json()}
    for pid in chosen:
        assert after[pid]["srp"] == repriced(before[pid]["srp"], 1000)
        assert {k: v for k, v in after[pid].items() if k != "srp"} == {k: v for k, v in before[pid].items() if k != "srp"}

    assert client.post("/inventory/bulk/products", json={"action": "reprice", "ids": chosen}, headers=iris).status_code == 422
    assert client.post("/inventory/bulk/products", json={"action": "deactivate", "ids": chosen}, headers=as_("ana")).status_code == 403
    job = client.post("/inventory/bulk/products", json={"action": "deactivate", "ids": chosen}, headers=iris).json()
    assert job["succeeded"] == 2
    off = client.get("/inventory/products", params={"state": "off"}, headers=iris).json()
    assert {p["id"] for p in off} == set(chosen)


def test_repriced_rounds_to_the_nearest_centavo():
    assert repriced(10_000, 500) == 10_500
    assert repriced(12_345, 1000) == 13_580  # 13,579.5 rounds up
    assert repriced(999, -1000) == 899  # 899.1
    assert repriced(0, 1000) == 0


# --- the queue ---------------------------------------------------------------------------


def wait_for(client, headers, job_id: str) -> dict:
    for _ in range(200):
        job = client.get(f"/jobs/{job_id}", headers=headers).json()
        if job["status"] == "done":
            return job
        time.sleep(0.02)
    raise AssertionError("the job never finished")


def test_a_big_job_is_queued_and_reports_its_progress(app, client, as_):
    app.state.jobs = JobQueue(batch_size=1, pause_seconds=0.01)
    paolo = as_("paolo")
    ids = [f["id"] for f in client.get("/sales/follow-ups", params={"division": "bnb", "who": "team"}, headers=paolo).json()["items"]]
    assert len(ids) == 3

    r = client.post("/sales/bulk/follow-ups", json={"action": "done", "ids": ids}, headers=paolo)
    assert r.status_code == 202
    assert r.json()["status"] in ("queued", "running", "done")
    job = wait_for(client, paolo, r.json()["id"])
    assert (job["processed"], job["succeeded"]) == (3, 3)
    # Only whoever started a job can see it.
    assert client.get(f"/jobs/{job['id']}", headers=as_("ana")).status_code == 404


def test_one_failing_batch_doesnt_stop_the_rest():
    calls: list[list[str]] = []

    def work(batch: list[str]) -> list:
        calls.append(batch)
        if "b" in batch:
            raise RuntimeError("boom")
        return [(i, None) for i in batch]

    queue = JobQueue(batch_size=1, pause_seconds=0)
    job = queue.submit("u1", "test", ["a", "b", "c", "a"], work)  # the repeat is dropped
    for _ in range(200):
        if job.status == "done":
            break
        time.sleep(0.01)
    assert calls == [["a"], ["b"], ["c"]]
    assert job.out()["succeeded"] == 2
    assert [f["id"] for f in job.failures] == ["b"]
    assert queue.get(job.id, "someone-else") is None


def test_a_conflict_fails_only_the_record_that_changed():
    records = Records(LocalBackend(None)).for_org(FIRST_ORG_ID)
    scope = Scope("b2c", "general")
    for n in ("a", "b", "c"):
        records.commit([Create({"_id": n, "_type": "customer", **scope.stamp(), "status": "lead"})])
    fresh = {d["_id"]: d["_rev"] for d in records.backend.fetch(Query("customer", {scope}))}
    items = [
        ("a", [Patch("a", {"status": "active"}, if_revision=fresh["a"])]),
        ("b", [Patch("b", {"status": "active"}, if_revision="an-old-revision")]),
        ("c", [Patch("c", {"status": "active"}, if_revision=fresh["c"])]),
    ]
    assert commit_items(records, items) == [("a", None), ("b", CHANGED), ("c", None)]
    status = {d["_id"]: d["status"] for d in records.backend.fetch(Query("customer", {scope}))}
    assert status == {"a": "active", "b": "lead", "c": "active"}


def test_switching_someone_off_stops_their_job(app, as_):
    as_("ana")
    with app.state.sessions() as db:
        ana = db.query(Profile).filter_by(email="ana@pharmacrm.test").one()
        ana.is_active = False
        db.commit()
        ana_id = ana.id
    ran = []
    outcomes = as_person(app.state.sessions, FIRST_ORG_ID, ana_id, ["x", "y"], lambda *args: ran.append(args) or [])
    assert outcomes == [("x", SWITCHED_OFF), ("y", SWITCHED_OFF)]
    assert ran == []


def test_each_record_is_checked_in_its_own_team(client, as_):
    """Ana, also given read-only B&B/General, can change her own team's customers but not those."""
    carmen = as_("carmen")
    ana_id = next(u["id"] for u in client.get("/admin/users", headers=carmen).json() if u["email"] == "ana@pharmacrm.test")
    grant = {"roleKey": "executive", "moduleKey": "bnb", "divisionCode": "bnb", "subdivisionCode": "general"}
    assert client.post(f"/admin/users/{ana_id}/assignments", json=grant, headers=carmen).status_code == 201

    ana = as_("ana")
    alma, mercado = (customer_id(client, ana, "bnb", n) for n in ("Dr. Alma Dizon", "Mercado Family Clinic"))
    job = client.post("/sales/bulk/customers", json={"action": "status", "ids": [alma, mercado], "status": "inactive"}, headers=ana).json()
    assert failures(job) == {mercado: NOT_ALLOWED}
    assert client.get(f"/sales/customers/{mercado}", headers=ana).json()["status"] == "active"

    # With no edit grant anywhere, it's refused before anything is queued.
    r = client.post("/sales/bulk/customers", json={"action": "status", "ids": [alma], "status": "lead"}, headers=as_("ramon"))
    assert r.status_code == 403


# --- rate limits ---------------------------------------------------------------------


def test_bulk_requests_have_their_own_limit(settings, records, files):
    settings = settings.model_copy(update={"rate_limit_enabled": True, "rate_bulk_per_minute": 2})
    app = build_app(settings, records, files)
    with TestClient(app) as client:
        token = client.post("/auth/login", json={"email": "ana@pharmacrm.test", "password": "demo1234"}).json()["accessToken"]
        ana = {"Authorization": f"Bearer {token}"}
        body = {"action": "status", "ids": ["nothing"], "status": "lead"}
        answers = [client.post("/sales/bulk/customers", json=body, headers=ana).status_code for _ in range(3)]
        assert answers == [202, 202, 429]
        # Ordinary saves aren't held up by it.
        assert client.get("/sales/summary?division=b2c", headers=ana).status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "kind"),
    [
        ("POST", "/sales/bulk/customers", "bulk"),
        ("POST", "/finance/bulk/approvals", "bulk"),
        ("GET", "/jobs/abc", "read"),
        ("POST", "/sales/customers", "write"),
    ],
)
def test_bulk_requests_are_recognised(method, path, kind):
    scope = {"type": "http", "method": method, "path": path, "headers": [], "query_string": b""}
    assert kind_of(Request(scope)) == kind


def test_sanity_rate_limit_is_waited_out():
    answers = iter([httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200, json={"result": 3})])
    waited: list[float] = []
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: next(answers)))
    sanity = SanityBackend("abc123", "production", "secret-token", "v2025-02-19", client, sleep=waited.append)
    assert sanity.count(Query("customer", {Scope("b2c", "general")})) == 3
    assert waited == [2.0]
