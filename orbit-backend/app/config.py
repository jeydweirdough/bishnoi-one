"""Settings, read from api/.env (see .env.example)."""

from functools import cached_property, lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.keys import SigningKeys

API_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = API_DIR / ".data"


class DatabaseSettings(BaseSettings):
    """Just what migrations need, so they run without the rest configured."""

    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # Accounts database. SQLite until Supabase is set up; to move, point this
    # at the Supabase Postgres connection string and run the migrations.
    database_url: str = f"sqlite:///{(DATA_DIR / 'accounts.db').as_posix()}"
    # On Postgres, the app should connect as a role that can read and write rows
    # but can't create, alter or drop anything; migrations then run as the
    # tables' owner through this URL. Unset: migrations use database_url.
    migration_database_url: str | None = None


class Settings(DatabaseSettings):
    environment: str = "development"
    # "Today" for follow-ups is decided in this timezone.
    timezone: str = "Asia/Manila"

    # Sign-in tokens are signed with this Ed25519 private key (PEM; in .env its
    # line breaks may be written as \n). Make one: uv run python -m app.tools.keys
    # Unset in development: one is made and kept in .data/signing-key.pem.
    jwt_private_key: SecretStr | None = None
    # Public keys of earlier private keys, so what they signed stays valid
    # until it expires. As JSON: JWT_PREVIOUS_PUBLIC_KEYS='["-----BEGIN PUBLIC KEY-----\n..."]'.
    jwt_previous_public_keys: list[str] = []
    signing_key_path: Path = DATA_DIR / "signing-key.pem"
    jwt_issuer: str = "pharma-crm-local"
    jwt_audience: str = "authenticated"
    session_hours: int = 10

    # The Orders app (its own screens; Orbit holds who may do what). Unset
    # until it's live: the sidebar shows no Orders link.

    # Sanity holds the business records. Without a project id the API uses a
    # JSON file instead, so the app runs before Sanity is connected.
    sanity_project_id: str = ""
    sanity_dataset: str = "production"
    sanity_token: str = ""
    sanity_api_version: str = "v2025-02-19"
    # Refuse to start against a dataset anyone can read. Only for throwaway data.
    allow_public_dataset: bool = False
    local_store_path: Path = DATA_DIR / "local-store.json"
    # Uploaded guarantee letters. See app/store/files.py before going to production.
    files_path: Path = DATA_DIR / "files"

    # --- the edges (app/main.py, app/ratelimit.py) ---
    # Browser origins allowed to call the API directly. None by default: the
    # browser never does; the Next server calls it for everyone. Exact origins
    # only, as JSON: CORS_ORIGINS='["https://crm.example.com"]'.
    cors_origins: list[str] = []
    # Host names the API answers to. Anything else gets 400, which stops
    # Host-header tricks. As JSON: ALLOWED_HOSTS='["api.internal", "127.0.0.1"]'.
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    # Addresses whose X-Forwarded-For is believed: the Next server, and any
    # reverse proxy in front of the API.
    trusted_proxies: list[str] = ["127.0.0.1", "::1"]

    # Requests per minute, per signed-in person (per address when not signed in).
    rate_limit_enabled: bool = True
    rate_reads_per_minute: int = 300
    rate_writes_per_minute: int = 60
    rate_uploads_per_minute: int = 10
    rate_anonymous_per_minute: int = 60
    # Bulk actions (each up to 500 items), and how the queue works through them:
    # this many items per round trip to the store, with this pause in between.
    rate_bulk_per_minute: int = 10
    bulk_batch_size: int = 50
    bulk_pause_seconds: float = 0.2
    # Run bulk jobs inside the request instead of in the background (tests).
    jobs_inline: bool = False

    @cached_property
    def signing_keys(self) -> SigningKeys:
        if self.jwt_private_key is not None:
            return SigningKeys.load(self.jwt_private_key.get_secret_value(), self.jwt_previous_public_keys)
        return SigningKeys.for_development(self.signing_key_path)

    @property
    def uses_sanity(self) -> bool:
        return bool(self.sanity_project_id)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _check(self) -> "Settings":
        if self.is_production and self.jwt_private_key is None:
            raise ValueError("Production needs JWT_PRIVATE_KEY (make one: uv run python -m app.tools.keys).")
        if self.uses_sanity and not self.sanity_token:
            raise ValueError("SANITY_TOKEN is required when SANITY_PROJECT_ID is set.")
        if self.environment == "production" and not self.uses_sanity:
            raise ValueError("Production needs Sanity; the local file store is for development only.")
        for origin in self.cors_origins:
            if "*" in origin or not origin.startswith(("https://", "http://")) or origin.rstrip("/") != origin:
                raise ValueError(
                    f"CORS_ORIGINS must list exact origins like https://crm.example.com, not {origin!r}. "
                    "Wildcards would let any site call the API from a visitor's browser."
                )
        if self.is_production and any(o.startswith("http://") for o in self.cors_origins):
            raise ValueError("In production, CORS_ORIGINS must be https://.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
