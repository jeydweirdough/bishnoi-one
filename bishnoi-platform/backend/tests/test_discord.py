"""Announcements kept in Discord, and the log sent there, against a fake Discord (tests/fake_discord.py)."""

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Announcement, User
from app.security import hash_password
from tests.conftest import PASSWORD, fresh_database
from tests.fake_discord import FakeDiscord

ANN = re.compile(r"^ANN-\d{8}-\d{4}$")


@pytest.fixture
def discord():
    with FakeDiscord() as notices, FakeDiscord() as logs:
        yield notices, logs


def live_app(tmp_path, discord, database_url=None):
    notices, logs = discord
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=database_url or fresh_database(tmp_path),
                        discord_enabled=True, discord_mode="live", discord_bot_token="bot-token",
                        discord_announcements_webhook_url=notices.webhook_url, discord_logs_webhook_url=logs.webhook_url)
    return create_app(settings)


def signed_in(app) -> tuple[TestClient, dict]:
    with app.state.sessions() as db:
        if not db.query(User).count():
            db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
            db.commit()
    client = TestClient(app)
    token = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}).json()["accessToken"]
    return client, {"Authorization": f"Bearer {token}"}


def data_in(message) -> dict:
    return json.loads(re.search(r"```json\n([\s\S]+?)\n```", message["content"]).group(1))


def test_an_announcement_is_a_thread_with_one_data_message(tmp_path, discord):
    notices, _ = discord
    app = live_app(tmp_path, discord)
    client, ana = signed_in(app)

    made = client.post("/platform/announcements", json={"title": "Stock count on Friday", "body": "Counting from 6 PM."}, headers=ana).json()["notice"]
    assert ANN.match(made["id"])
    thread = notices.thread_named(made["id"])
    assert len(thread) == 1 and data_in(thread[0])["title"] == "Stock count on Friday"

    # A change edits the same message: still one per row.
    client.patch(f"/platform/announcements/{made['id']}", json={"publish": True, "title": "Stock count on Saturday"}, headers=ana)
    thread = notices.thread_named(made["id"])
    assert len(thread) == 1 and data_in(thread[0])["title"] == "Stock count on Saturday" and data_in(thread[0])["publishedAt"]
    assert [n["title"] for n in client.get("/public/notices").json()["notices"]] == ["Stock count on Saturday"]

    # The next id that day follows on.
    second = client.post("/platform/announcements", json={"title": "Second"}, headers=ana).json()["notice"]
    assert second["id"][:-4] == made["id"][:-4] and int(second["id"][-4:]) == int(made["id"][-4:]) + 1


def test_a_restart_reads_them_back_from_discord(tmp_path, discord):
    database = fresh_database(tmp_path)
    client, ana = signed_in(live_app(tmp_path, discord, database))
    made = client.post("/platform/announcements", json={"title": "Read me back", "publish": True, "body": "x" * 3000}, headers=ana).json()["notice"]
    # Over 2000 characters: the data goes as an attached data-<id>.json.
    thread = discord[0].thread_named(made["id"])
    assert thread[0]["attachments"][0]["filename"] == f"data-{made['id'].lower()}.json"

    again = live_app(tmp_path, discord, database)  # a new server, nothing in memory
    client, ana = signed_in(again)
    notices = client.get("/platform/announcements", headers=ana).json()["notices"]
    assert [(n["id"], n["title"], len(n["body"])) for n in notices] == [(made["id"], "Read me back", 3000)]


def test_deleting_removes_the_thread(tmp_path, discord):
    client, ana = signed_in(live_app(tmp_path, discord))
    made = client.post("/platform/announcements", json={"title": "Short-lived"}, headers=ana).json()["notice"]
    assert client.delete(f"/platform/announcements/{made['id']}", headers=ana).status_code == 204
    assert discord[0].thread_named(made["id"]) is None
    assert client.get("/platform/announcements", headers=ana).json()["notices"] == []


def test_when_discord_is_down_nothing_is_saved(tmp_path, discord):
    client, ana = signed_in(live_app(tmp_path, discord))
    discord[0].down = True
    r = client.post("/platform/announcements", json={"title": "Won't stick"}, headers=ana)
    assert r.status_code == 503 and "nothing was saved" in r.json()["detail"]
    discord[0].down = False
    assert client.get("/platform/announcements", headers=ana).json()["notices"] == []


def test_old_announcements_move_out_of_the_database(tmp_path, discord):
    database = fresh_database(tmp_path)
    first = live_app(tmp_path, discord, database)
    with first.state.sessions() as db:
        db.add(Announcement(id="old-one", kind="announcement", level="info", title="From before", created_by="ana@example.com"))
        db.commit()
    again = live_app(tmp_path, discord, database)
    client, ana = signed_in(again)
    assert [n["id"] for n in client.get("/platform/announcements", headers=ana).json()["notices"]] == ["old-one"]
    with again.state.sessions() as db:
        assert db.query(Announcement).count() == 0
    assert discord[0].thread_named("old-one")


def test_the_log_is_a_thread_a_day(tmp_path, discord):
    app = live_app(tmp_path, discord)
    client, ana = signed_in(app)
    client.post("/platform/announcements", json={"title": "Logged"}, headers=ana)
    app.state.logs.flush()
    logs = discord[1]
    day = next(m["embeds"][0]["title"] for m in logs.messages["5000"] if m["embeds"][0]["title"].startswith("LOG-PLATFORM-"))
    assert re.fullmatch(r"LOG-PLATFORM-\d{8}", day)
    lines = logs.thread_named(day)
    titles = [m["embeds"][0]["title"] for m in lines]
    assert "announcement.drafted" in titles
    line = lines[titles.index("announcement.drafted")]["embeds"][0]
    assert line["footer"]["text"] == "ana@example.com" and any(f["value"] == "notice: Logged" for f in line["fields"])
