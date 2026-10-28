"""Finance's explicit Python-only PostgreSQL option; TLS is always verified."""
import ssl
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
import os


def connection_options(address):
    url = make_url(address.replace("postgres://", "postgresql://", 1))
    allowed = {"sslmode", "channel_binding", "connect_timeout", "application_name"}
    if set(url.query) - allowed or any(not isinstance(v, str) for v in url.query.values()):
        raise ValueError("Unsupported PostgreSQL connection options; keep the original settings private and contact IT.")
    if url.query.get("sslmode", "verify-full") not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("Finance requires a verified encrypted PostgreSQL connection.")
    binding = url.query.get("channel_binding", "prefer")
    if binding not in {"prefer", "require"}:
        raise ValueError("Finance requires supported SCRAM channel-binding settings.")
    try:
        timeout = int(url.query.get("connect_timeout", "10"))
    except ValueError:
        raise ValueError("Use a PostgreSQL connection timeout between 1 and 30 seconds.") from None
    if not 1 <= timeout <= 30:
        raise ValueError("Use a PostgreSQL connection timeout between 1 and 30 seconds.")
    return url, binding, dict(user=url.username, password=url.password, host=url.host,
        port=url.port or 5432, database=url.database, timeout=timeout,
        ssl_context=ssl.create_default_context(),
        application_name=url.query.get("application_name", "bishnoi-finance"))


def channel_bound_connection(required):
    from pg8000.dbapi import Connection, InterfaceError

    class SecureConnection(Connection):
        def __init__(self, **kwargs):
            self._finance_scram_plus = False
            super().__init__(**kwargs)

        def handle_AUTHENTICATION_REQUEST(self, data, context):
            code = int.from_bytes(data[:4], "big")
            if required:
                if code == 10:
                    if b"SCRAM-SHA-256-PLUS\x00" not in data[4:]:
                        raise InterfaceError("The database did not offer required channel binding.")
                    self._finance_scram_plus = True
                elif code in (3, 5) or (code == 0 and not self._finance_scram_plus):
                    raise InterfaceError("The database did not use required channel binding.")
            result = super().handle_AUTHENTICATION_REQUEST(data, context)
            if required and code == 10 and self.auth.mechanism_name != 'SCRAM-SHA-256-PLUS':
                raise InterfaceError('Required channel binding was not negotiated.')
            return result
    return SecureConnection


def python_engine(address):
    url, binding, options = connection_options(address)
    connection = channel_bound_connection(binding == "require")
    public_url = url.set(drivername="postgresql+pg8000", query={})
    args = {"creator": lambda: connection(**options), "pool_pre_ping": True}
    if os.environ.get("VERCEL"):
        args["poolclass"] = NullPool
    else:
        args["pool_timeout"] = 10
    return create_engine(public_url, **args)
