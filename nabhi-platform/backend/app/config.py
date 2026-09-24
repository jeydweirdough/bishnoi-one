"""Settings, read from backend/.env (see .env.example).

These are what the platform starts with. The ones a Platform Admin changes
while it runs (sign-in rules, health-check timing, response targets) live in
the database instead (app/platform_settings.py), and start from the values here.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = API_DIR / ".data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    # This app's own database: its staff, sessions and the platform's records.
    database_url: str = f"sqlite:///{(DATA_DIR / 'platform.db').as_posix()}"
    # The first Platform Admin, made when the database has no accounts at all:
    # for a host you can't run the users tool against (Vercel + a database it
    # can reach and you can't). Once anyone exists these are ignored; remove the
    # password afterwards.
    first_admin_email: str | None = None
    first_admin_name: str = "Platform Admin"
    first_admin_password: SecretStr | None = None
    # How long a sign-in lasts, until changed under Settings > Security.
    session_hours: int = 10
    # Wrong passwords allowed per email before sign-in waits, and for how long.
    login_attempts: int = 5
    login_lockout_minutes: int = 15

    # The platform, as its screens show it.
    org_name: str = "Nabhi"
    org_currency: str = "PHP"
    org_minor_units: int = 2
    org_locale: str = "en-PH"
    org_timezone: str = "Asia/Manila"

    # Host names this API answers to. Anything else gets 400.
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    # Browser origins allowed to call the API directly. None by default.
    cors_origins: list[str] = []

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _check(self) -> "Settings":
        for origin in self.cors_origins:
            if "*" in origin or not origin.startswith(("https://", "http://")) or origin.rstrip("/") != origin:
                raise ValueError(f"CORS_ORIGINS must list exact origins like https://app.example.com, not {origin!r}.")
        if self.session_hours < 1:
            raise ValueError("SESSION_HOURS must be at least 1.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
