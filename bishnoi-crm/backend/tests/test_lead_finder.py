"""Find leads with AI: what a chatbot found is checked (missing details, type,
look-alikes already in the CRM) and saved only as the person ticks it."""

from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)


def lead(name="Mercury Drug Davao Bajada", **extra):
    return {"name": name, "type": "customer", "city": "Davao City", "phone": "+63 82 221 0000", "source": "https://example.test/mercury", "why": "Near two hospitals", **extra}


def test_found_leads_are_checked_against_the_crm(client, crew):  # noqa: F811
    company(client, crew["ria"], "Mercury Drug Davao Bajada", city="Davao City", phone="082 221 0000")
    got = client.get("/leads/finder", headers=crew["ria"]).json()
    assert {"code": "customer", "name": "Customer"} in got["types"]
    r = client.post("/leads/check", json={"leads": [lead(), lead("Rose Pharmacy Toril", phone=None, source=None, type="hospitalx")]}, headers=crew["ria"])
    assert r.status_code == 200, r.text
    first, second = r.json()["items"]
    assert first["matches"][0]["name"] == "Mercury Drug Davao Bajada" and "Same phone number" in first["matches"][0]["why"]
    assert first["type"] == "customer" and first["problems"] == []
    assert second["matches"] == [] and second["type"] is None
    assert "No source link: check it before saving" in second["problems"] and any("isn't one of yours" in p for p in second["problems"])


def test_ticked_leads_become_the_persons_customers_with_a_call_to_make(client, crew):  # noqa: F811
    r = client.post("/leads/save", json={"leads": [lead("Rose Pharmacy Toril"), lead("Davao Doctors Clinic", type="nonsense")]}, headers=crew["ria"])
    assert r.status_code == 200, r.text
    saved = r.json()["saved"]
    assert [s["name"] for s in saved] == ["Rose Pharmacy Toril", "Davao Doctors Clinic"]
    rose = client.get(f"/companies/{saved[0]['id']}", headers=crew["ria"]).json()
    assert rose["owner"]["name"] == "Ria" and rose["status"] == "customer"
    assert "Found with AI search" in rose["notes"] and "https://example.test/mercury" in rose["notes"]
    tasks = client.get(f"/activities?company={saved[0]['id']}", headers=crew["ria"]).json()["items"]
    assert any(t["subject"].startswith("Call new lead") for t in tasks)
