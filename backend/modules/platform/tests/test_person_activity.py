"""Activity per person (2026-11-18, step 4F): an employee's own Bishnoi One entries, paged by time, only for the
company's administrators. Each app's part is that app's /admin/audit?person=."""

from modules.platform.tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def test_an_employees_own_activity_page_by_page(client, getmeds):  # noqa: F811 (fixtures)
    h, rio, jade = getmeds["owner"]["h"], getmeds["rio"], getmeds["jade"]
    client.post("/identity/login", json={"email": "rio@getmeds.test", "password": "not-his-password-1"})
    url = f"/identity/access/people/{rio['id']}/activity"
    everything = client.get(url, headers=h).json()
    assert everything["entries"] and all(e["actor"] == "rio@getmeds.test" for e in everything["entries"])
    assert everything["more"] is False
    first = client.get(url, params={"limit": 1}, headers=h).json()
    assert len(first["entries"]) == 1 and first["more"] is (len(everything["entries"]) > 1)
    rest = client.get(url, params={"before": first["entries"][0]["at"]}, headers=h).json()["entries"]
    assert [e["id"] for e in first["entries"] + rest] == [e["id"] for e in everything["entries"]]
    # Jade's are hers only.
    assert all(e["actor"] == "jade@getmeds.test" for e in client.get(f"/identity/access/people/{jade['id']}/activity", headers=h).json()["entries"])
    # Only the company's administrators read it.
    assert client.get(url, headers=jade["h"]).status_code == 403
