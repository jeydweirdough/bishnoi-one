"""The first administrator comes from the settings, only into an empty database."""

from pydantic import SecretStr
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import User
from app.permissions import ROLE_ADMIN_ID


def settings(tmp_path, **extra) -> Settings:
    return Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'a.db').as_posix()}", **extra)


def test_first_admin_is_made_once(tmp_path):
    first = settings(tmp_path, first_admin_email="Boss@Example.com", first_admin_name="Boss", first_admin_password=SecretStr("a long enough password 1"))
    app = create_app(first)
    with app.state.sessions() as db:
        users = db.scalars(select(User)).all()
        assert [(u.email, u.role_id) for u in users] == [("boss@example.com", ROLE_ADMIN_ID)]
    # Started again with other settings: someone exists, so nothing more is made.
    again = settings(tmp_path, first_admin_email="other@example.com", first_admin_password=SecretStr("a long enough password 2"))
    with create_app(again).state.sessions() as db:
        assert db.scalar(select(User).where(User.email == "other@example.com")) is None
