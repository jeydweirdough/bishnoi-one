"""Settings, read from backend/.env (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = API_DIR / ".data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    # This app's own database: its users, sessions and data.
    database_url: str = f"sqlite:///{(DATA_DIR / 'admin.db').as_posix()}"
    # The online database (Neon) that `python -m app.tools.copy_database backup`
    # copies into .data/backups/ each night. Unset: DATABASE_URL itself.
    backup_from: str | None = None
    # The first administrator, made when the database has no accounts at all:
    # for a host you can't run the users tool against (Vercel + Supabase).
    # Once anyone exists these are ignored; remove the password afterwards.
    first_admin_email: str | None = None
    first_admin_name: str = "Administrator"
    first_admin_password: SecretStr | None = None
    # How long a sign-in lasts.
    session_hours: int = 10
    # Signing in with a Bishnoi One account: the platform's API. Its public key
    # is fetched from there (app/platform_pass.py); PLATFORM_PUBLIC_KEY, when set,
    # is used instead. Neither set: only this app's own accounts sign in.
    platform_api_url: str | None = None
    platform_public_key: str | None = None
    # Wrong passwords allowed per email before sign-in waits, and for how long.
    login_attempts: int = 5
    login_lockout_minutes: int = 15

    # The company this app belongs to, as its screens show it.
    org_name: str = "Bishnoi One"
    org_currency: str = "PHP"
    org_minor_units: int = 2
    org_locale: str = "en-PH"
    org_timezone: str = "Asia/Manila"

    # Host names this API answers to. Anything else gets 400.
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    @field_validator("allowed_hosts", mode="after")
    @classmethod
    def _host_names_only(cls, hosts: list[str]) -> list[str]:
        """Host names, as the check compares them: "127.0.0.1:8302", "https://x.vercel.app/"
        and " name " are read as 127.0.0.1, x.vercel.app and name (a port there matched nothing)."""
        out: list[str] = []
        for host in hosts:
            name = host.strip()
            if "://" in name:
                name = name.split("://", 1)[1]
            name = name.split("/", 1)[0]
            if name.count(":") == 1:
                name = name.split(":", 1)[0]
            if name and name not in out:
                out.append(name)
        return out

    @model_validator(mode="after")
    def _this_computer_always(self):
        """Off production, this computer's own names are always allowed, so an app's
        own screens and the Platform's checks can't be locked out by ALLOWED_HOSTS."""
        if self.environment != "production" and "*" not in self.allowed_hosts:
            for name in ("localhost", "127.0.0.1"):
                if name not in self.allowed_hosts:
                    self.allowed_hosts.append(name)
        return self
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
        if self.discord_mode.lower() not in ("mock", "live"):
            raise ValueError("DISCORD_MODE is mock or live.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
