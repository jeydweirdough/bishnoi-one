"""The API as one ready-made app, for hosts that import it instead of running
main.py (Vercel: pyproject.toml's [tool.vercel] entrypoint). Its settings come
from the host's environment variables, as they would from backend/.env.

If it can't start (a setting missing or malformed, the database out of reach),
it doesn't just crash: every request gets a 503 saying which kind of problem it
is and which setting to look at, and the full error goes to the host's logs.
The answer never carries the error's text, which may hold an address or a
password.
"""

import logging
import os
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy.exc import OperationalError

from app.main import create_app

log = logging.getLogger("crm.server")


def _diagnose(error: Exception) -> dict:
    if isinstance(error, ValidationError):
        fields = sorted({str(e["loc"][0]).upper() for e in error.errors() if e.get("loc")})
        return {"problem": "settings", "check": fields or ["the environment variables"],
                "hint": "A setting is malformed. Lists are JSON, e.g. ALLOWED_HOSTS=[\"your-api.vercel.app\"]."}
    if isinstance(error, SettingsError):
        # "error parsing value for field "allowed_hosts" from source ...": the name only.
        field = re.search(r'field "(\w+)"', str(error))
        return {"problem": "settings", "check": [field.group(1).upper() if field else "the environment variables"],
                "hint": "A setting is malformed. Lists are JSON, e.g. ALLOWED_HOSTS=[\"your-api.vercel.app\"]."}
    if isinstance(error, OperationalError):
        return {"problem": "database", "check": ["DATABASE_URL"],
                "hint": "The database can't be reached or refused the sign-in. On Supabase use the pooler address "
                        "(port 6543), and write a # in the password as %23."}
    if isinstance(error, OSError):
        return {"problem": "files", "check": ["DATABASE_URL"],
                "hint": "It tried to write to the disk, which this host doesn't allow. Set DATABASE_URL to a Postgres database."}
    return {"problem": "startup", "check": ["the host's logs"], "hint": "The full error is in the logs."}


def _unavailable(diagnosis: dict) -> FastAPI:
    fallback = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @fallback.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def unavailable(request: Request, path: str) -> JSONResponse:
        return JSONResponse({"ok": False, "app": "crm", **diagnosis}, status_code=503)

    return fallback


if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
    # Without it the API would make a SQLite file on a disk it can't write to.
    app = _unavailable({"problem": "settings", "check": ["DATABASE_URL"],
                        "hint": "DATABASE_URL isn't set for this environment. Add it (Settings > Environment Variables) and redeploy."})
else:
    try:
        app = create_app()
    except Exception as error:  # noqa: BLE001 (report it, whatever it is)
        log.exception("The API could not start")
        app = _unavailable(_diagnose(error))
