"""Settings, read from backend/.env (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = API_DIR / ".data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    # This app's own database: its users, sessions and data.
    database_url: str = f"sqlite:///{(DATA_DIR / 'finance.db').as_posix()}"
    # How long a sign-in lasts.
    session_hours: int = 10
    # Wrong passwords allowed per email before sign-in waits, and for how long.
    login_attempts: int = 5
    login_lockout_minutes: int = 15

    # The company this app belongs to, as its screens show it.
    org_name: str = "Nabhi"
    org_currency: str = "PHP"
    org_minor_units: int = 2
    org_locale: str = "en-PH"
    org_timezone: str = "Asia/Manila"

    # Host names this API answers to. Anything else gets 400.
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    # Browser origins allowed to call the API directly. None by default.
    cors_origins: list[str] = []

    # Other Nabhi apps allowed to ask for tax (the /integration endpoints), as
    # name:key pairs in JSON, e.g. ["crm:<a long random key>"]. The app sends
    # its key in X-Nabhi-Key. Empty: nothing outside can ask.
    integration_keys: list[SecretStr] = []

    # A released fund that's liquidated is due back, with its receipts, this
    # many days after it's released.
    liquidate_within_days: int = 7

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
        for key in self.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if not name or len(secret) < 24:
                raise ValueError("INTEGRATION_KEYS must list name:key pairs, each key at least 24 characters.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
