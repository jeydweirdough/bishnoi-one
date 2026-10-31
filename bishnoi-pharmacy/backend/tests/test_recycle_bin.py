"""Data clean-up and the recycle bin in Pharmacy (2026-10-30, app/recycle_bin.py)."""


def test_a_patient_goes_to_the_bin_and_comes_back(client, ana, ben):
    assert client.get("/data-cleanup/kinds", headers=ben).status_code == 403
    p = client.post("/patients", json={"fullName": "Test Patient", "kind": "patient"}, headers=ana)
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    r = client.post("/data-cleanup/kinds/patients/delete", json={"ids": [pid]}, headers=ana)
    assert r.status_code == 200, r.text
    assert client.get(f"/patients/{pid}", headers=ana).status_code == 404
    entry = client.get("/data-cleanup/bin", headers=ana).json()["items"][0]
    assert client.post(f"/data-cleanup/bin/{entry['id']}/restore", headers=ana).status_code == 200
    assert client.get(f"/patients/{pid}", headers=ana).status_code == 200
