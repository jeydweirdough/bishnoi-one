"""An older copy of the API (a Nabhi.exe not yet updated) refuses a database
a newer one has already brought forward."""

import pytest
from sqlalchemy import create_engine, text

from app.config import Settings
from app.main import create_app
from app.migrate import DatabaseTooNew


def test_an_older_copy_refuses_a_newer_database(tmp_path):
    url = f"sqlite:///{(tmp_path / 'inventory.db').as_posix()}"
    create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=url))
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("UPDATE nbin_alembic_version SET version_num = '9999_from_a_newer_nabhi'"))
    engine.dispose()
    with pytest.raises(DatabaseTooNew, match="Update Nabhi.exe"):
        create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=url))
