"""Who monitors whom (2026-11-18, step 4E): its own list, made from the chart, kept when people move, edited by hand."""

from sqlalchemy import select

from modules.platform import org_push, watchers
from modules.platform.models import Company, Identity, Watcher
from modules.platform.tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)
from modules.platform.tests.test_unit_heads import unit


def seen_by(app, person_id):
    with app.state.sessions() as db:
        p = db.get(Identity, person_id)
        company = db.get(Company, p.company_id)
        chart = next(x for x in org_push.chart(db, company)["people"] if x["email"] == p.email.lower())["managers"]
        placed = org_push.placement(db, p)
        return chart, placed["managers"] if placed else []


def test_the_chart_makes_watchers_who_stay_after_a_move_until_removed(app, client, getmeds):
    h, olive, rio, jade = getmeds["owner"]["h"], getmeds["owner"], getmeds["rio"], getmeds["jade"]
    top = unit(client, h, "department", "Sales", heads=[olive["id"]])
    rx = unit(client, h, "division", "Rx", parent=top["id"], heads=[rio["id"]])
    b2b = unit(client, h, "division", "B2B", parent=top["id"])
    client.put(f"/identity/organisation/people/{jade['id']}", json={"mainUnitId": rx["id"]}, headers=h)

    listed = client.get(f"/identity/access/people/{jade['id']}/watchers", headers=h).json()["watchers"]
    assert {(w["email"], w["source"], w["onChart"]) for w in listed} == {("rio@getmeds.test", "chart", True), ("olive@getmeds.test", "chart", True)}
    assert all(w["since"] and w["addedBy"] is None for w in listed)
    # While the chart gives Rio, removing Rio is refused.
    assert client.delete(f"/identity/access/people/{jade['id']}/watchers/{rio['id']}", headers=h).status_code == 409

    # Jade moves to B2B: Rio no longer heads her unit but keeps watching her, after the chart's own managers.
    client.put(f"/identity/organisation/people/{jade['id']}", json={"mainUnitId": b2b["id"]}, headers=h)
    assert seen_by(app, jade["id"]) == (["olive@getmeds.test", "rio@getmeds.test"],) * 2
    rio_row = next(w for w in client.get(f"/identity/access/people/{jade['id']}/watchers", headers=h).json()["watchers"] if w["id"] == rio["id"])
    assert rio_row["source"] == "chart" and rio_row["onChart"] is False

    # Removed by hand: gone, and the next chart change doesn't bring Rio back.
    r = client.delete(f"/identity/access/people/{jade['id']}/watchers/{rio['id']}", headers=h)
    assert r.status_code == 200, r.text
    assert [w["email"] for w in r.json()["watchers"]] == ["olive@getmeds.test"]
    client.patch(f"/identity/organisation/units/{b2b['id']}", json={"name": "B2B sales"}, headers=h)
    assert seen_by(app, jade["id"]) == (["olive@getmeds.test"],) * 2
    with app.state.sessions() as db:
        entry = db.execute(select(Watcher).where(Watcher.watched_id == jade["id"])).scalars().all()
        assert [w.watcher_id for w in entry] == [olive["id"]]


def test_an_administrator_adds_a_watcher_by_hand_and_nobody_else_can(app, client, getmeds):
    h, olive, rio, jade = getmeds["owner"]["h"], getmeds["owner"], getmeds["rio"], getmeds["jade"]
    url = f"/identity/access/people/{jade['id']}/watchers"
    # Not an administrator: neither reads nor changes.
    assert client.get(url, headers=jade["h"]).status_code == 403
    assert client.post(url, json={"watcherId": rio["id"]}, headers=rio["h"]).status_code == 403
    assert client.delete(f"{url}/{olive['id']}", headers=rio["h"]).status_code == 403
    # Not themselves; only this company's people.
    assert client.post(url, json={"watcherId": jade["id"]}, headers=h).status_code == 422
    assert client.post(url, json={"watcherId": "nobody"}, headers=h).status_code == 422

    r = client.post(url, json={"watcherId": rio["id"]}, headers=h)
    assert r.status_code == 201, r.text
    [w] = r.json()["watchers"]
    assert (w["id"], w["source"], w["addedBy"], w["onChart"]) == (rio["id"], "added", "olive@getmeds.test", False)
    assert seen_by(app, jade["id"])[1] == ["rio@getmeds.test"]  # in her pass too, with no place on the chart
    # Removing one who isn't watching: not found.
    assert client.delete(f"{url}/{olive['id']}", headers=h).status_code == 404
    assert client.delete(f"{url}/{rio['id']}", headers=h).status_code == 200
    assert seen_by(app, jade["id"])[1] == []


def test_the_upgrade_fills_watchers_from_todays_chart(app, client, getmeds):
    """Migration 0030 calls watchers.record over every company: the same code the chart changes use."""
    h, olive, jade = getmeds["owner"]["h"], getmeds["owner"], getmeds["jade"]
    sales = unit(client, h, "department", "Sales", heads=[olive["id"]])
    client.put(f"/identity/organisation/people/{jade['id']}", json={"mainUnitId": sales["id"]}, headers=h)
    with app.state.sessions() as db:
        db.query(Watcher).delete()
        db.commit()
        assert watchers.record(db.execute) == 1
        assert watchers.record(db.execute) == 0  # never twice
        db.commit()
        assert [(w.watched_id, w.watcher_id, w.source) for w in db.scalars(select(Watcher))] == [(jade["id"], olive["id"], "chart")]
