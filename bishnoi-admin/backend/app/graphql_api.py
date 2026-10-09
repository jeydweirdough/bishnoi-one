"""GraphQL for reading: one request per page, only the fields the page shows.

    POST /graphql   {"query": "...", "variables": {...}}

Each field is answered by the REST route that answers the same question, so
the two can't disagree: the same queries, the same permission, the same
limits. The machinery (calling a route, the limits, the endpoint) is
app/graphql_core.py, the same file in every app.

Why: every page asked who you are, then what isn't set up (the menu's red
counts), then its own list: three requests, each checking the session again.
Here the frame is one request and the page one more, and a record's page and
its title share theirs.
"""

import strawberry
from graphql import GraphQLError
from strawberry.scalars import JSON

from app.graphql_core import graphql_router, route
from app.routers import admin, auth, operations, unset


def _reads(path: str):
    if path not in operations.READS:
        raise GraphQLError(f"There's no {path} list.", extensions={"code": "NOT_FOUND", "status": 404})
    return operations.READS[path]


@strawberry.type
class Query:
    # --- the frame every page shares ---

    @strawberry.field
    def me(self, info: strawberry.Info) -> JSON | None:
        return route(auth.me, info)

    @strawberry.field
    def unset(self, info: strawberry.Info) -> JSON | None:
        return route(unset.unset, info)

    # --- Home ---

    @strawberry.field
    def dashboard(self, info: strawberry.Info) -> JSON | None:
        return route(admin.executive_dashboard, info)

    @strawberry.field
    def notifications(self, info: strawberry.Info, unread_only: bool | None = None) -> JSON | None:
        return route(admin.list_notifications, info, unread_only=unread_only)

    # --- compliance and office ---

    @strawberry.field
    def permits(self, info: strawberry.Info, category: str | None = None, status: str | None = None) -> JSON | None:
        return route(admin.list_permits, info, category=category, status_filter=status)

    @strawberry.field
    def immigration(self, info: strawberry.Info, document_type: str | None = None) -> JSON | None:
        return route(admin.list_immigration, info, doc_type=document_type)

    @strawberry.field
    def documents(self, info: strawberry.Info, category: str | None = None, missing: bool | None = None) -> JSON | None:
        return route(admin.list_documents, info, category=category, missing=missing)

    @strawberry.field
    def properties(self, info: strawberry.Info, property_type: str | None = None, missing: bool | None = None) -> JSON | None:
        return route(admin.list_properties, info, property_type=property_type, missing=missing)

    @strawberry.field
    def tickets(self, info: strawberry.Info, status: str | None = None, priority: str | None = None) -> JSON | None:
        return route(admin.list_tickets, info, status_filter=status, priority=priority)

    @strawberry.field
    def ticket(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(admin.get_ticket, info, ticket_id=id)

    # --- fleet and travel: vehicles, fleet-cards, travel, devices ---

    @strawberry.field
    def records(self, info: strawberry.Info, path: str) -> JSON | None:
        return route(_reads(path)[0], info)

    @strawberry.field
    def record(self, info: strawberry.Info, path: str, id: str) -> JSON | None:
        return route(_reads(path)[1], info, record_id=id)

    # --- administration ---

    @strawberry.field
    def users(self, info: strawberry.Info) -> JSON | None:
        return route(admin.list_users, info)

    @strawberry.field
    def roles(self, info: strawberry.Info) -> JSON | None:
        return route(admin.list_roles, info)

    @strawberry.field
    def audit(self, info: strawberry.Info, before: int | None = None, limit: int | None = None, action: str | None = None, actor: str | None = None) -> JSON | None:
        return route(admin.audit_log, info, before=before, limit=limit, action=action, actor_id=actor)


router = graphql_router(Query)
