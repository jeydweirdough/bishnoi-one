"""Media: approved materials, current only between approval and expiry and for
their divisions; a file (small) or a link; each opening counted."""

from datetime import date, timedelta

from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)

PDF = b"%PDF-1.4 a deck"
TODAY = date.today().isoformat()


def add(client, ana, **body):
    r = client.post("/admin/media", json={"title": "Onco One deck", "approvedOn": TODAY, **body}, headers=ana)
    assert r.status_code == 201, r.text
    return r.json()


def test_reps_see_what_is_current_for_them(client, ana, crew):
    teams = {t["name"]: t["id"] for t in client.get("/team-names", headers=ana).json()}
    add(client, ana, title="Everyone's", url="https://drive.example.com/deck")
    add(client, ana, title="North only", url="https://drive.example.com/n", onlyTeams=[teams["North"]])
    add(client, ana, title="Expired", url="https://drive.example.com/x", approvedOn="2025-01-01", expiresOn="2025-12-31")
    add(client, ana, title="Not yet", url="https://drive.example.com/y", approvedOn=(date.today() + timedelta(days=3)).isoformat())
    assert [m["title"] for m in client.get("/media", headers=crew["ria"]).json()["items"]] == ["Everyone's", "North only"]
    assert [m["title"] for m in client.get("/media", headers=crew["sam"]).json()["items"]] == ["Everyone's"]
    assert len(client.get("/media?all=true", headers=ana).json()["items"]) == 4
    # Reps don't add them.
    assert client.post("/admin/media", json={"title": "x", "approvedOn": TODAY}, headers=crew["ria"]).status_code == 403


def test_a_file_and_its_openings(client, ana, crew):
    item = add(client, ana)
    r = client.put(f"/admin/media/{item['id']}/file", files={"file": ("deck.pdf", PDF, "application/pdf")}, headers=ana)
    assert r.status_code == 200 and r.json()["kind"] == "file"
    assert client.put(f"/admin/media/{item['id']}/file", files={"file": ("x.exe", b"MZ...", "application/octet-stream")}, headers=ana).status_code == 422
    acme = company(client, crew["ria"])
    assert client.post(f"/media/{item['id']}/opened", json={"companyId": acme["id"]}, headers=crew["ria"]).json() == {"url": None, "file": True}
    got = client.get(f"/media/{item['id']}/file", headers=crew["ria"])
    assert got.status_code == 200 and got.content == PDF
    assert client.get("/media?all=true", headers=ana).json()["items"][0]["opened30d"] == 1
