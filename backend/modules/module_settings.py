"""Where a module's settings come from, now that every module shares one backend/.env and,
on a server, one environment.

A setting is read, first found wins:

1. what the code passes (tests: ``Settings(database_url=...)``);
2. ``<MODULE>_<SETTING>`` in the environment, then in backend/.env (e.g. ``CRM_DATABASE_URL``);
3. ``<SETTING>`` in the environment, then in backend/.env (e.g. ``DATABASE_URL``, shared);
4. the default in the module's config.py.

So on Coolify one DATABASE_URL serves every module (tables never clash: each module has its
own prefix and its own Alembic version table), and on this computer each module can keep its
own SQLite file. ``Settings(_env_file=None)`` still reads no file at all, prefixed or not.
"""

from __future__ import annotations

from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, PydanticBaseSettingsSource


class _ModuleEnv(EnvSettingsSource):
    """The environment's <MODULE>_<SETTING> names; `skip` settings are never read with the prefix."""

    def __init__(self, settings_cls: type[BaseSettings], prefix: str, skip: tuple[str, ...]):
        self._skip = set(skip)
        super().__init__(settings_cls, env_prefix=prefix)

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        if field_name in self._skip:
            return None, field_name, False
        return super().get_field_value(field, field_name)


class _ModuleDotEnv(DotEnvSettingsSource):
    """backend/.env's <MODULE>_<SETTING> lines."""

    def __init__(self, settings_cls: type[BaseSettings], prefix: str, skip: tuple[str, ...], env_file, encoding):
        self._skip = set(skip)
        super().__init__(settings_cls, env_file=env_file, env_file_encoding=encoding, env_prefix=prefix)

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        if field_name in self._skip:
            return None, field_name, False
        return super().get_field_value(field, field_name)


def module_sources(
    prefix: str,
    settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource,
    skip: tuple[str, ...] = (),
) -> tuple[PydanticBaseSettingsSource, ...]:
    """For a module's ``Settings.settings_customise_sources``: the module's own names before the shared ones."""
    env_file = getattr(dotenv_settings, "env_file", None)
    encoding = getattr(dotenv_settings, "env_file_encoding", None)
    return (
        init_settings,
        _ModuleEnv(settings_cls, prefix, skip),
        _ModuleDotEnv(settings_cls, prefix, skip, env_file, encoding),
        env_settings,
        dotenv_settings,
        file_secret_settings,
    )


# ---------------------------------------------------------------------------------------------
# One address for the whole backend (2026-11-17). Every module answers at BACKEND_URL + its path
# (main.py MODULES), so the address of one module, for another module or for the Platform's
# Applications, is worked out instead of set: BACKEND_URL=http://127.0.0.1:8300 on this computer,
# the backend's internal address on the server (e.g. http://10.0.1.1:8300).

DEFAULT_BACKEND_URL = "http://127.0.0.1:8300"

# Each module's path in the one backend.
MODULE_PATHS: dict[str, str] = {
    "platform": "/platform",
    "crm": "/crm",
    "inventory": "/inventory",
    "finance": "/finance",
    "admin": "/admin",
    "pharmacy": "/pharmacy",
    "in_licensing": "/in-licensing",
    "regulatory": "/regulatory",
}

# The settings one module reads another's address from, and that module's path. Unset, each
# is BACKEND_URL + path (link_defaults); set in the environment or backend/.env, shared or with
# a module's prefix (CRM_INVENTORY_API_URL), it wins as before. A link still needs its key,
# which the Platform gives while connected (each module's platform_links.py).
LINK_SETTINGS: dict[str, str] = {
    "PLATFORM_API_URL": "/platform",
    "CRM_API_URL": "/crm",
    "INVENTORY_API_URL": "/inventory",
    "FINANCE_API_URL": "/finance",
    "PHARMACY_API_URL": "/pharmacy",
}


def _dotenv(env_file) -> dict[str, str]:
    from pathlib import Path

    from dotenv import dotenv_values

    path = Path(env_file) if env_file else None
    if path is None or not path.is_file():
        return {}
    return {k.upper(): v for k, v in dotenv_values(path).items() if v not in (None, "")}


def backend_url(env_file=None) -> str:
    """BACKEND_URL from the environment, else from backend/.env, else this computer's; no / at the end."""
    import os

    value = os.environ.get("BACKEND_URL") or _dotenv(env_file).get("BACKEND_URL") or DEFAULT_BACKEND_URL
    return value.strip().rstrip("/")


def link_defaults(env_file=None) -> str:
    """Tells every module where the others are: BACKEND_URL and each *_API_URL in LINK_SETTINGS
    go into the environment as BACKEND_URL + path, unless the environment or backend/.env already
    says (shared or prefixed: a prefixed setting wins anyway). Called by backend/main.py before
    the modules start; tests never call it, so a module's tests stay unconnected as before.
    Returns BACKEND_URL."""
    import os

    file_values = _dotenv(env_file)
    url = backend_url(env_file)
    os.environ.setdefault("BACKEND_URL", url)
    for name, path in LINK_SETTINGS.items():
        if name not in os.environ and name not in file_values:
            os.environ[name] = url + path
    return url
