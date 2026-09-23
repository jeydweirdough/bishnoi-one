from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health():
    app = create_app(Settings(_env_file=None, allowed_hosts=["testserver"]))
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "app": "pharmacy"}
