"""GraphQL for reading: one request per page, only the fields the page shows.

    POST /graphql   {"query": "...", "variables": {...}}

The rule across Bishnoi One: what a page reads comes through here; everything
else stays REST: saving (its checks and audit log), sign-in, files (uploads,
imports, exports, prints), app-to-app calls and outside services (webhooks).

Each field here is answered by the REST route that answers the same question
(`route(...)` below), so the two can't disagree: the same queries, the same
reach (app/scope.py), and the same permission, read off the route itself
(app/access.py `require` marks it), with its arguments held to the route's
own limits (a months count of 2 to 36, a search of at most 100 characters).

Why: a page used to make a call per piece (the customer, its types, the
people, its quotes...), and each call checked the session and opened the
company again: 5 to 7 database queries before any data. One request checks
once. The frame every page shares (who you are, the menu's counts) is one
more, so a page costs two requests.

The machinery (calling a route, the limits, the endpoint) is app/graphql_core.py,
the same file in every app.
"""

import strawberry
from strawberry.scalars import JSON

from app.graphql_core import build, graphql_router, route
from app.routers import activities, attention, auth, companies, customer_types, deals, field, insights, kpis, people, quotes, retention, sales, settings as settings_router, unset


@strawberry.type
class Ref:
    id: str
    name: str


@strawberry.type
class Can:
    edit: bool
    delete: bool


@strawberry.type
class Contact:
    id: str
    name: str
    job_title: str | None
    email: str | None
    phone: str | None


@strawberry.type
class Company:
    id: str
    code: str | None
    name: str
    status: str
    price_group_code: str | None
    industry: str | None
    lead_source: str | None
    website: str | None
    email: str | None
    phone: str | None
    city: str | None
    country: str | None
    owner: Ref | None
    team: Ref | None
    contact_count: int | None
    last_activity_at: str | None
    updated_at: str | None
    extra: JSON | None
    can: Can | None
    # On one customer only (its page), not in lists:
    address: str | None
    notes: str | None
    created_at: str | None
    links: JSON | None
    linked_here: JSON | None
    contacts: list[Contact] | None
    activities: JSON | None


@strawberry.type
class CompanyPage:
    items: list[Company]
    total: int


@strawberry.type
class Person:
    id: str
    name: str
    team: Ref | None
    is_me: bool


@strawberry.type
class CustomerType:
    code: str
    name: str
    color: str
    sort_order: int
    is_active: bool
    companies: int
    only_teams: list[str] | None
    except_teams: list[str] | None


@strawberry.type
class Query:
    # Every page's frame
    @strawberry.field(description="Who is signed in, their company, role and permissions (the REST /auth/me).")
    def me(self, info: strawberry.Info) -> JSON | None:
        return route(auth.me, info)

    @strawberry.field(description="How many of each thing isn't set up yet, for the menu's red counts.")
    def unset(self, info: strawberry.Info) -> JSON | None:
        return route(unset.unset, info)

    # Customers
    @strawberry.field
    def companies(
        self, info: strawberry.Info, q: str | None = None, status: str | None = None, owner: str | None = None, sort: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> CompanyPage | None:
        page = route(companies.list_companies, info, q=q, status_=status, owner=owner, sort=sort, limit=limit, offset=offset)
        return CompanyPage(items=[build(Company, c) for c in page["items"]], total=page["total"])

    @strawberry.field
    def company(self, info: strawberry.Info, id: str) -> Company | None:
        return build(Company, route(companies.read_company, info, company_id=id))

    @strawberry.field(name="customerTypes")
    def customer_types(self, info: strawberry.Info) -> list[CustomerType] | None:
        return [build(CustomerType, t) for t in route(customer_types.list_types, info)]

    @strawberry.field(description="The people this person may give records to.")
    def people(self, info: strawberry.Info) -> list[Person] | None:
        return [build(Person, p) for p in route(people.assignable, info)]

    @strawberry.field(description="A form as people fill it in (Settings → Forms).")
    def form(self, info: strawberry.Info, entity: str) -> JSON | None:
        return route(settings_router.read_form, info, entity=entity)

    # On a customer's page
    @strawberry.field
    def quotes(self, info: strawberry.Info, company: str | None = None, owner: str | None = None, task: str | None = None, limit: int | None = None) -> JSON | None:
        return route(quotes.list_quotes, info, company=company, owner=owner, task=task, limit=limit)

    @strawberry.field
    def activities(self, info: strawberry.Info, owner: str | None = None, state: str | None = None, company: str | None = None, limit: int | None = None) -> JSON | None:
        return route(activities.list_activities, info, owner=owner, state=state, company=company, limit=limit)

    @strawberry.field(name="activitySummary")
    def activity_summary(self, info: strawberry.Info, owner: str | None = None) -> JSON | None:
        return route(activities.summary, info, owner=owner)

    @strawberry.field(name="fieldDoctors")
    def field_doctors(self, info: strawberry.Info, limit: int | None = None) -> JSON | None:
        return route(field.list_doctors, info, limit=limit)

    @strawberry.field
    def visits(self, info: strawberry.Info, company: str | None = None, limit: int | None = None) -> JSON | None:
        return route(field.list_visits, info, company=company, limit=limit)

    @strawberry.field(name="doctorBalance")
    def doctor_balance(self, info: strawberry.Info, company_id: str) -> JSON | None:
        return route(field.read_doctor_balance, info, company_id=company_id)

    @strawberry.field
    def deals(
        self, info: strawberry.Info, company: str | None = None, owner: str | None = None, state: str | None = None, sort: str | None = None, limit: int | None = None
    ) -> JSON | None:
        return route(deals.list_deals, info, company=company, owner=owner, state=state, sort=sort, limit=limit)

    # Home
    @strawberry.field
    def attention(self, info: strawberry.Info) -> JSON | None:
        return route(attention.read_attention, info)

    @strawberry.field(name="dealsSummary")
    def deals_summary(self, info: strawberry.Info, state: str | None = None, owner: str | None = None) -> JSON | None:
        return route(deals.summary, info, state=state, owner=owner)

    @strawberry.field(name="salesTrend")
    def sales_trend(self, info: strawberry.Info, months: int | None = None, view: str | None = None) -> JSON | None:
        return route(sales.read_trend, info, months=months, view=view)

    @strawberry.field(name="salesResults")
    def sales_results(self, info: strawberry.Info, view: str | None = None, period: str | None = None) -> JSON | None:
        return route(sales.read_results, info, view=view, period=period)

    @strawberry.field
    def retention(self, info: strawberry.Info, view: str | None = None) -> JSON | None:
        return route(retention.read_retention, info, view=view)

    @strawberry.field(name="fieldPerformance")
    def field_performance(self, info: strawberry.Info, month: str | None = None) -> JSON | None:
        return route(field.performance, info, month=month)

    @strawberry.field(name="peopleInsights")
    def people_insights(self, info: strawberry.Info) -> JSON | None:
        return route(insights.people_insights, info)

    @strawberry.field
    def performance(self, info: strawberry.Info, view: str | None = None, month: str | None = None, role: str | None = None) -> JSON | None:
        """Results against targets (GET /kpi-scorecard): one's own, or everyone one's role reaches."""
        return route(kpis.scorecard, info, view=view, month=month, role=role)


router = graphql_router(Query)
