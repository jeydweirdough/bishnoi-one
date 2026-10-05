"""The CRM's audit log in Discord, a thread a day, and only what was committed (fake Discord)."""

import re

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, fresh_database, role_id, sign_in
from tests.fake_discord import CHANNEL, FakeDiscord


def test_audit_lines_go_to_a_thread_a_day(tmp_path):
    with FakeDiscord() as discord:
        settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), files_dir=tmp_path / "files",
                            discord_enabled=True, discord_mode="live", discord_bot_token="bot", discord_logs_webhook_url=discord.webhook_url)
        app = create_app(settings)
        with app.state.sessions() as db:
            db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Administrator")))
            db.commit()
        client = TestClient(app)
        ana = bearer(sign_in(client))
        assert client.post("/companies", json={"name": "Bayview Pediatrics"}, headers=ana).status_code == 201
        app.state.logs.flush()

        day = next(m["embeds"][0]["title"] for m in discord.messages[CHANNEL])
        assert re.fullmatch(r"LOG-CRM-\d{8}", day)
        lines = [m["embeds"][0] for m in discord.thread_named(day)]
        added = next(line for line in lines if line["title"].startswith("company."))
        assert added["footer"]["text"] == "ana@example.com (getmeds)"  # whose company: one CRM, several companies
        assert any("Bayview Pediatrics" in f["value"] for f in added["fields"])
        app.state.tenants.close()
