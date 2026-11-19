"""Around every page, one request: the same answers as its parts."""

from .test_tax_api import ana, app, client  # noqa: F401 (fixtures)


def test_one_request_for_the_frame(client, ana):
    frame = client.get("/finance/frame", headers=ana)
    assert frame.status_code == 200, frame.text
    assert frame.json()["me"] == client.get("/auth/me", headers=ana).json()
    assert client.get("/finance/frame").status_code == 401
