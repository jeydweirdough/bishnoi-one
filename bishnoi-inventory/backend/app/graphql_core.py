"""GraphQL's machinery, the same in every Bishnoi One app (only app/graphql_api.py,
the fields, is each app's own). Keep the copies identical.

The rule across Bishnoi One: what a page reads comes through GraphQL, in one
request with only the fields it shows; everything else stays REST: saving
(its checks and audit log), sign-in, files (uploads, imports, exports,
prints), app-to-app calls and outside services (webhooks).

Each field is answered by the REST route that answers the same question
(`route(...)`), so the two can't disagree: the same queries, the same reach,
and the same permission, read off the route itself (app/access.py `require`
marks it), with its arguments held to the route's own limits.

The apps' database code is synchronous, so POST /graphql is a normal (sync)
route, run in FastAPI's worker threads like every other, never on the event
loop. Queries are limited in depth, size and aliases; outside development
the schema can't be listed (introspection is off); an unexpected error is
logged and shown as a plain line, never its details.
"""

import inspect
import logging
import re
import typing
from functools import cache
from typing import Annotated, Any, get_args, get_origin

import strawberry
from fastapi import APIRouter, HTTPException, Request
from fastapi.params import Depends as DependsParam
from fastapi.params import Query as QueryParam
from graphql import GraphQLError
from graphql.validation import NoSchemaIntrospectionCustomRule
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from strawberry.extensions import AddValidationRules, MaskErrors, MaxAliasesLimiter, MaxTokensLimiter, QueryDepthLimiter

from app.access import Access, CurrentAccess
from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app.models import User

log = logging.getLogger(__name__)


# --- calling a REST route, held to its own rules ----------------------------------------------


def _depends(annotation) -> Any:
    """The dependency function behind an `Annotated[..., Depends(fn)]` parameter, if any."""
    if get_origin(annotation) is Annotated:
        for meta in get_args(annotation)[1:]:
            if isinstance(meta, DependsParam):
                return meta.dependency
    return None


# The dependencies that only hand over what the endpoint already has: who is
# signed in, their access, the database and the settings. Any other one is a
# check, and is run only if it's a permission (`require` marks it).
_PLAIN = {_depends(a) for a in (CurrentAccess, CurrentUser, DB, SettingsDep)}


def route(fn, info: strawberry.Info, **given):
    """Calls a REST route function as FastAPI would: its permission checked, its
    dependencies filled from this request, its arguments validated against the
    route's own limits, and its HTTP errors turned into this field's error."""
    try:
        try:
            return _call(fn, info, given)
        except OperationalError:
            # The database dropped the connection (Neon closes idle ones). The
            # session is rolled back so this request's other fields still run,
            # and this one is tried once more on a fresh connection.
            info.context["db"].rollback()
            try:
                return _call(fn, info, given)
            except OperationalError:
                info.context["db"].rollback()
                raise GraphQLError("The database didn't answer. Try again in a moment.", extensions={"code": "UNAVAILABLE", "status": 503}) from None
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, str) else "That couldn't be read."
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(e.status_code, "BAD_INPUT")
        raise GraphQLError(detail, extensions={"code": code, "status": e.status_code}) from None


def _call(fn, info: strawberry.Info, given: dict):
    ctx = info.context
    kwargs: dict[str, Any] = {}
    hints = typing.get_type_hints(fn, include_extras=True)
    for name, param in inspect.signature(fn).parameters.items():
        annotation = hints.get(name, param.annotation)
        dep = _depends(annotation)
        if dep is not None:
            needed = getattr(dep, "permission", None)
            if needed:
                ctx["access"].require(needed)
            elif dep not in _PLAIN:
                # A check GraphQL doesn't know how to run (not a permission):
                # refused, never skipped. Add the route's check to app/access.py
                # `require`'s style, or leave that read on REST.
                raise GraphQLError(f"{fn.__name__} can't be read through GraphQL.")
            base = get_args(annotation)[0]
            value = {Access: ctx["access"], User: ctx["me"], Session: ctx["db"], Settings: ctx["settings"]}.get(base)
            if value is None:
                raise GraphQLError(f"{fn.__name__} needs {base}, which GraphQL doesn't provide.")
            kwargs[name] = value
            continue
        default = param.default
        rule = default if isinstance(default, QueryParam) else None
        if given.get(name) is not None:
            try:
                kwargs[name] = TypeAdapter(Annotated[annotation, rule] if rule else annotation).validate_python(given[name])
            except ValidationError as e:
                raise GraphQLError(f"{name}: {e.errors()[0]['msg']}", extensions={"code": "BAD_INPUT", "status": 422}) from None
        elif rule is not None:
            if rule.is_required():
                raise GraphQLError(f"{name} is needed.", extensions={"code": "BAD_INPUT", "status": 422})
            kwargs[name] = rule.default
        elif default is not inspect.Parameter.empty:
            kwargs[name] = default
    return fn(**kwargs)


# --- REST answers as GraphQL objects ------------------------------------------------------------


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.title() for w in rest)


def build(cls, data: dict | None):
    """A GraphQL object from a REST answer (camelCase keys), nested types included."""
    if data is None:
        return None
    return cls(**{f.python_name: _convert(f.type, data.get(_camel(f.python_name))) for f in cls.__strawberry_definition__.fields})


def _convert(kind, raw):
    if raw is None:
        return None
    inner = getattr(kind, "of_type", kind)  # Optional / list wrappers
    if hasattr(kind, "of_type") and isinstance(raw, list):
        return [_convert(inner, r) for r in raw]
    target = getattr(inner, "of_type", inner)
    if hasattr(target, "__strawberry_definition__") and isinstance(raw, dict):
        return build(target, raw)
    return raw


# --- the endpoint ----------------------------------------------------------------------------------


def _hide(error: GraphQLError) -> bool:
    """Our own errors (a route's plain message) are shown; anything unexpected is logged and hidden."""
    original = getattr(error, "original_error", None)
    if original is None or isinstance(original, GraphQLError):
        return False
    log.error("GraphQL %s: %s", ".".join(str(p) for p in (error.path or [])), original, exc_info=original)
    return True


LIMITS = [
    QueryDepthLimiter(max_depth=6),
    MaxTokensLimiter(max_token_count=3000),
    MaxAliasesLimiter(max_alias_count=15),
    MaskErrors(should_mask_error=_hide, error_message="That part of the page couldn't be read. Try again in a moment."),
]


class GraphQLIn(BaseModel):
    query: str = Field(max_length=20_000)
    variables: dict[str, Any] | None = None
    operation_name: str | None = Field(None, alias="operationName", max_length=100)


def graphql_router(query_type: type) -> APIRouter:
    """POST /graphql for this app's fields (its Query type)."""
    router = APIRouter(tags=["graphql"])

    @cache
    def schema(listable: bool) -> strawberry.Schema:
        extensions = [*LIMITS] if listable else [*LIMITS, AddValidationRules([NoSchemaIntrospectionCustomRule])]
        return strawberry.Schema(query=query_type, extensions=extensions)

    @router.post("/graphql")
    def graphql(body: GraphQLIn, request: Request, access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep) -> dict:
        """One page's reads, in one request. Signing in is checked once, here."""
        result = schema(not settings.is_production).execute_sync(
            body.query,
            variable_values=body.variables,
            operation_name=body.operation_name,
            context_value={"access": access, "me": me, "db": db, "settings": settings, "request": request},
        )
        out: dict[str, Any] = {"data": result.data}
        if result.errors:
            out["errors"] = [{"message": re.sub(r"\s+", " ", e.message).strip(), "path": e.path, "extensions": e.extensions or {"code": "BAD_INPUT"}} for e in result.errors]
        return out

    return router
