"""Settings, read from backend/.env (see .env.example)."""

import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = API_DIR / ".data"


def on_a_server() -> bool:
    """Whether this runs on a hosting service, which says so in its own settings."""
    return bool(os.environ.get("VERCEL_ENV")) or any(name.startswith("COOLIFY_") for name in os.environ)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    # This app's own database: its users, sessions and data.
    database_url: str = f"sqlite:///{(DATA_DIR / 'finance.db').as_posix()}"
    # The first administrator, made when the database has no accounts at all:
    # for a host you can't run the users tool against (Vercel + Supabase).
    # Once anyone exists these are ignored; remove the password afterwards.
    first_admin_email: str | None = None
    first_admin_name: str = "Administrator"
    first_admin_password: SecretStr | None = None
    # How long a sign-in lasts.
    session_hours: int = 10
    # Signing in with a Bishnoi One account: the platform's public key, base64 (its
    # /pass/key). Unset: only this app's own accounts sign in.
    platform_public_key: str | None = None
    # Bishnoi One Platform's API: where Finance asks what it's linked to.
    platform_api_url: str | None = None
    # Finance's connect key, made on the platform's Connections page. With it,
    # the platform says what Finance is linked to and the keys between them
    # (app/platform_links.py), and CRM_API_URL, CRM_API_KEY and INTEGRATION_KEYS are no longer needed.
    # Unset: those settings are used, as before.
    platform_app_key: SecretStr | None = None
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
    def _where_it_runs(self):
        """Nothing to set for where it runs (decided 2026-10-27). On a server
        (Vercel, Coolify) it's production unless ENVIRONMENT says otherwise; on
        this computer, development. In production with no ALLOWED_HOSTS it
        answers to whatever name it's reached by: nothing here is built from that
        name, and every request is checked by its sign-in or key."""
        if "environment" not in self.model_fields_set and on_a_server():
            self.environment = "production"
        if "allowed_hosts" not in self.model_fields_set and self.environment == "production":
            self.allowed_hosts = ["*"]
        return self

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

    # Other Bishnoi One apps allowed to ask for tax (the /integration endpoints), as
    # name:key pairs in JSON, e.g. ["crm:<a long random key>"]. The app sends
    # its key in X-Bishnoi-Key. Empty: nothing outside can ask.
    integration_keys: list[SecretStr] = []

    # A released fund that's liquidated is due back, with its receipts, this
    # many days after it's released.
    liquidate_within_days: int = 7

    # Bishnoi One CRM, whose customers an invoice is made out to: its API
    # (https://...), and the key it gave Finance (one of its INTEGRATION_KEYS,
    # the part after "finance:"). Unset: the customer is typed on the invoice.
    crm_api_url: str | None = None
    crm_api_key: SecretStr | None = None
    # Which company's customers and prices, in a CRM that keeps one database per
    # company: its short name on Bishnoi One Platform (2MG's). Sent with every
    # call (X-Bishnoi-Company). Unset: none is named, which the CRM accepts only
    # off production, where it falls back to its own default company.
    crm_company: str | None = None

    @property
    def crm_linked(self) -> bool:
        return bool(self.crm_api_url and self.crm_api_key)

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
        if self.crm_api_url and (not self.crm_api_url.startswith(("https://", "http://")) or self.crm_api_url.endswith("/")):
            raise ValueError(f"CRM_API_URL is an address like https://crm-api.example.com, with no / at the end, not {self.crm_api_url!r}.")
        if self.crm_company is not None:
            # Kept as the CRM keeps it (bishnoi-crm app/tenants.py): lower case, 2 to 40 letters, numbers and dashes.
            self.crm_company = self.crm_company.strip().lower() or None
            if self.crm_company and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,38}[a-z0-9]", self.crm_company):
                raise ValueError(f"CRM_COMPANY is a company's short name on Bishnoi One Platform (letters, numbers and dashes), not {self.crm_company!r}.")
        for key in self.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if not name or len(secret) < 24:
                raise ValueError("INTEGRATION_KEYS must list name:key pairs, each key at least 24 characters.")
        if self.discord_mode.lower() not in ("mock", "live"):
            raise ValueError("DISCORD_MODE is mock or live.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
