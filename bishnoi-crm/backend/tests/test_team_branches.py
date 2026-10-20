"""Branches of a division (from the 2026 org chart): a team can be part of a
division, one level deep, and the list shows each division with its branches."""


def team(client, ana, name, **extra):
    r = client.post("/admin/teams", json={"name": name, **extra}, headers=ana)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_branch_is_part_of_a_division_one_level_deep(client, ana):
    b2b = team(client, ana, "B2B")
    nbd = team(client, ana, "NBD", parentId=b2b["id"])
    crr = team(client, ana, "CRR", parentId=b2b["id"])
    team(client, ana, "Alpha")  # sorts before B2B
    assert nbd["parentId"] == b2b["id"]
    names = [t["name"] for t in client.get("/admin/teams", headers=ana).json()]
    assert names.index("B2B") < names.index("CRR") < names.index("NBD")  # the division, then its branches
    # One level: not under a branch, not itself, and a division with branches stays one.
    assert client.post("/admin/teams", json={"name": "Deep", "parentId": nbd["id"]}, headers=ana).status_code == 422
    assert client.patch(f"/admin/teams/{b2b['id']}", json={"parentId": b2b["id"]}, headers=ana).status_code == 422
    other = team(client, ana, "Other")
    assert client.patch(f"/admin/teams/{b2b['id']}", json={"parentId": other["id"]}, headers=ana).status_code == 422
    # A branch can stand on its own again.
    assert client.patch(f"/admin/teams/{crr['id']}", json={"parentId": None}, headers=ana).json()["parentId"] is None
