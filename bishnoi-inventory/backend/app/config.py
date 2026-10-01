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
    database_url: str = f"sqlite:///{(DATA_DIR / 'inventory.db').as_posix()}"
    # The first administrator, made when the database has no accounts at all:
    # for a host you can't run the users tool against (Vercel + a database it
    # can reach and you can't). Once they exist these are ignored; remove the
    # password afterwards.
    first_admin_email: str | None = None
    first_admin_name: str = "Administrator"
    first_admin_password: SecretStr | None = None
    # How long a sign-in lasts.
    session_hours: int = 10
    # Signing in with a Nabhi account: the platform's public key, base64 (its
    # /pass/key). Unset: only this app's own accounts sign in.
    platform_public_key: str | None = None
    # Wrong passwords allowed per email before sign-in waits, and for how long.
    login_attempts: int = 5
    login_lockout_minutes: int = 15

    # A batch expiring within this many days is flagged as expiring soon.
    expiry_warning_days: int = 90
    # Stock with no outbound movement in this many days counts as dead stock.
    dead_stock_days: int = 180

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

    # Discord (app/discord.py): this app's log goes to a thread per day in the
    # logs channel. Off until DISCORD_ENABLED=true; DISCORD_MODE=live
    # really posts, mock keeps everything on this machine. See .env.example.
    discord_enabled: bool = False
    discord_mode: str = "mock"
    discord_bot_token: SecretStr | None = None
    discord_logs_webhook_url: SecretStr | None = None
    discord_max_per_minute: int = 30

    # Other Nabhi apps allowed to read the catalogue and stock levels (the
    # /integration endpoints), as name:key pairs in JSON, e.g.
    # ["crm:<a long random key>"]. The app sends its key in X-Nabhi-Key. Empty:
    # nothing outside can read them.
    integration_keys: list[SecretStr] = []

    @property
    def discord_mock_dir(self) -> Path:
        """Where mock mode keeps its tables: beside a SQLite database (so each test has its own), else .data/."""
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.removeprefix("sqlite:///")).parent / "discord-mock"
        return DATA_DIR / "discord-mock"

    @staticmethod
    def secret(value: SecretStr | None) -> str | None:
        return value.get_secret_value() if value else None

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
        if self.expiry_warning_days < 1 or self.dead_stock_days < 1:
            raise ValueError("EXPIRY_WARNING_DAYS and DEAD_STOCK_DAYS must be at least 1.")
        if self.discord_mode.lower() not in ("mock", "live"):
            raise ValueError("DISCORD_MODE is mock or live.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
