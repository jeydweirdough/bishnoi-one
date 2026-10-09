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
    database_url: str = f"sqlite:///{(DATA_DIR / 'crm.db').as_posix()}"
    # The online database (Neon) that `python -m app.tools.copy_database backup`
    # copies into .data/backups/ each night. Unset: DATABASE_URL itself.
    backup_from: str | None = None
    # Where uploaded files (guarantee letters) are kept.
    files_dir: Path = DATA_DIR / "files"
    # The first administrator, made when the database has no accounts at all:
    # for a host you can't run the users tool against (Vercel + a database it
    # can reach and you can't). Once they exist these are ignored; remove the
    # password afterwards.
    first_admin_email: str | None = None
    first_admin_name: str = "Administrator"
    first_admin_password: SecretStr | None = None
    # Which company's database the first administrator is made in (each company
    # has its own: app/tenants.py). Unset: DEFAULT_COMPANY on this computer, and
    # none in production, where a company's administrators come from Bishnoi One.
    first_admin_company: str | None = None
    # How long a sign-in lasts.
    session_hours: int = 10
    # Signing in with a Bishnoi One account: the platform's public key, base64 (its
    # /pass/key). Unset: only this app's own accounts sign in.
    platform_public_key: str | None = None
    # Bishnoi One Platform's API: where the CRM asks whether a company is
    # registered, active and given the CRM (app/company.py). Each company has a
    # database of its own (app/tenants.py), made the first time it's used.
    platform_api_url: str | None = None
    # The CRM's connect key, made on the platform's Connections page. With it,
    # the platform says what the CRM is linked to (Inventory, Finance,
    # Pharmacy) and the keys between them (app/platform_links.py), and the
    # INVENTORY_/FINANCE_/PHARMACY_ settings and INTEGRATION_KEYS below are
    # no longer needed. Unset: those settings are used, as before.
    platform_app_key: SecretStr | None = None
    # On this computer only (never in production): the company a request is for
    # when it doesn't say, and the companies allowed while the platform isn't
    # set up here (PLATFORM_API_URL unset).
    default_company: str | None = "getmeds"
    # Not a setting: the company of the request these settings are for, set
    # by app/deps.py, and sent on to the other apps (X-Bishnoi-Company).
    company: str | None = None
    # Not a setting either: the company's own words (app/terms.py), set by app/deps.py.
    terms: dict | None = None
    dev_companies: list[str] = ["getmeds", "northwind"]
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

    # Email notifications (app/email.py): sent through an email delivery
    # service's SMTP server. Off until EMAIL_ENABLED=true; EMAIL_MODE=smtp
    # really sends, mock keeps it on this machine. CRM_APP_URL is where the
    # CRM's screens are, for the link in each email. See .env.example.
    email_enabled: bool = False
    email_mode: str = "mock"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_starttls: bool = True
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str | None = None
    crm_app_url: str | None = None

    # Bishnoi One Inventory, where the product list and stock come from: its API
    # (https://...), and the key it gave this app (one of its INTEGRATION_KEYS,
    # the part after "crm:"). Unset: products are kept here, by hand.
    inventory_api_url: str | None = None
    inventory_api_key: SecretStr | None = None
    # Inventory's screens, for the "Add it in Inventory" link. Optional.
    inventory_app_url: str | None = None

    # Bishnoi One Finance, which works out tax (the price rules' last step): its API,
    # and the key it gave this app (one of its INTEGRATION_KEYS, the part after
    # "crm:"). Unset: quotes are priced without tax.
    finance_api_url: str | None = None
    finance_api_key: SecretStr | None = None

    # Bishnoi One Order, where orders are made: its API (https://...), and the key it
    # gave this app (sent as X-Bishnoi-Key). "Raise order" on a ready quote sends
    # it there (app/orders.py has the payload). Unset: the button is not shown.
    orders_api_url: str | None = None
    orders_api_key: SecretStr | None = None

    # Bishnoi One Pharmacy, where a pharmacist checks a quote marked Rx before it's
    # ordered (app/pharmacy.py): its API, and the key it gave this app (one of
    # its INTEGRATION_KEYS, the part after "crm:"). Unset: an Rx quote can't be
    # sent for checking, so it can't be ordered.
    pharmacy_api_url: str | None = None
    pharmacy_api_key: SecretStr | None = None

    # The other Bishnoi One apps allowed to read the CRM's customers (the
    # /integration/customers endpoints: Finance invoices them), as name:key
    # pairs in JSON, e.g. ["finance:<a long random key>"]. The app sends its key
    # in X-Bishnoi-Key. Empty: nothing outside can read them.
    integration_keys: list[SecretStr] = []

    # No CONNECTIONS_KEY any more: outside services are connected on the platform,
    # and the CRM's own secrets use the key it gives (app/connections.py).

    @property
    def inventory_linked(self) -> bool:
        return bool(self.inventory_api_url and self.inventory_api_key)

    @property
    def finance_linked(self) -> bool:
        return bool(self.finance_api_url and self.finance_api_key)

    @property
    def orders_linked(self) -> bool:
        return bool(self.orders_api_url and self.orders_api_key)

    @property
    def pharmacy_linked(self) -> bool:
        return bool(self.pharmacy_api_url and self.pharmacy_api_key)

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
        for url in (self.inventory_api_url, self.inventory_app_url):
            if url and (not url.startswith(("https://", "http://")) or url.endswith("/")):
                raise ValueError(f"INVENTORY_API_URL and INVENTORY_APP_URL are addresses like https://inventory-api.example.com, with no / at the end, not {url!r}.")
        if self.finance_api_url and (not self.finance_api_url.startswith(("https://", "http://")) or self.finance_api_url.endswith("/")):
            raise ValueError(f"FINANCE_API_URL is an address like https://finance-api.example.com, with no / at the end, not {self.finance_api_url!r}.")
        if self.pharmacy_api_url and (not self.pharmacy_api_url.startswith(("https://", "http://")) or self.pharmacy_api_url.endswith("/")):
            raise ValueError(f"PHARMACY_API_URL is an address like https://pharmacy-api.example.com, with no / at the end, not {self.pharmacy_api_url!r}.")
        if self.session_hours < 1:
            raise ValueError("SESSION_HOURS must be at least 1.")
        if self.discord_mode.lower() not in ("mock", "live"):
            raise ValueError("DISCORD_MODE is mock or live.")
        for key in self.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if not name or len(secret) < 24:
                raise ValueError("INTEGRATION_KEYS must list name:key pairs, each key at least 24 characters.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
