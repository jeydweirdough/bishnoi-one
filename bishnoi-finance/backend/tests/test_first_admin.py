"""The first administrator comes from the settings, only into an empty database."""

from pydantic import SecretStr
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import User


def settings(tmp_path, **extra) -> Settings:
    return Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'f.db').as_posix()}", **extra)


def test_first_admin_is_made_once(tmp_path):
    first = settings(tmp_path, first_admin_email="Boss@Example.com", first_admin_name="Boss", first_admin_password=SecretStr("a long enough password 1"))
    with create_app(first).state.sessions() as db:
        assert [(u.email, u.role.name) for u in db.scalars(select(User))] == [("boss@example.com", "Administrator")]
    # Started again with other settings: someone exists, so nothing more is made.
    again = settings(tmp_path, first_admin_email="other@example.com", first_admin_password=SecretStr("a long enough password 2"))
    with create_app(again).state.sessions() as db:
        assert db.scalar(select(User).where(User.email == "other@example.com")) is None


def test_no_settings_no_admin(tmp_path):
    with create_app(settings(tmp_path)).state.sessions() as db:
        assert db.scalar(select(User)) is None


def test_a_weak_password_is_not_used(tmp_path):
    weak = settings(tmp_path, first_admin_email="boss@example.com", first_admin_password=SecretStr("short"))
    with create_app(weak).state.sessions() as db:
        assert db.scalar(select(User)) is None
