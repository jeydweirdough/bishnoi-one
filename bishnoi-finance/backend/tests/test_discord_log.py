"""Finance's log in Discord: every change and sign-in as a line, a thread a day (fake Discord)."""

import re

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.security import hash_password

from .fake_discord import CHANNEL, FakeDiscord
from .test_auth import PASSWORD, bearer, sign_in
from .test_tax_api import REGISTRATION


def test_changes_and_sign_ins_are_logged_a_thread_a_day(tmp_path):
    with FakeDiscord() as discord:
        settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
                            discord_enabled=True, discord_mode="live", discord_bot_token="bot", discord_logs_webhook_url=discord.webhook_url)
        app = create_app(settings)
        with app.state.sessions() as db:
            db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
            db.commit()
        client = TestClient(app)
        ana = bearer(sign_in(client))
        assert sign_in(client, password="wrong").status_code == 401
        assert client.put("/tax/profile", json=REGISTRATION, headers=ana).status_code == 200
        app.state.logs.flush()

        day = next(m["embeds"][0]["title"] for m in discord.messages[CHANNEL])
        assert re.fullmatch(r"LOG-FINANCE-\d{8}", day)
        lines = [m["embeds"][0] for m in discord.thread_named(day)]
        assert [line["title"] for line in lines] == ["auth.signed_in", "auth.sign_in_failed", "/tax/profile changed"]
        assert lines[-1]["footer"]["text"] == "Ana Reyes · ana@example.com"
