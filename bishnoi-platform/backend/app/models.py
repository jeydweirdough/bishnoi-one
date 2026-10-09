"""The platform's records. Every table is nbpl_ (Bishnoi One PLatform).

Two kinds of people live here, and they are kept apart on purpose:

- **Staff** (`User`, nbpl_users) sign in to this app: Platform Admins run it,
  Support works its tickets and incidents.
- **Platform users** (`Identity`, nbpl_identities) are the people at the
  companies, with the applications each one may use and their role in each.
  They don't sign in here; this is the register of who they are.

Each application still has its own sign-in; what's here is the record of who
should reach what, and what is happening across all of it.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


def _one_of(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    quoted = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=name)


# ---- Staff: who signs in here --------------------------------------------------

STAFF_ROLES = ("admin", "member")  # admin: Platform Admin. member: Support.


class User(Base):
    __tablename__ = "nbpl_users"
    __table_args__ = (_one_of("role", STAFF_ROLES, "nbpl_user_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="member")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Every session started before this ends (see deps.current_user).
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_sign_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SignInSession(Base):
    """One sign-in. The browser holds the token; only its hash is kept here."""

    __tablename__ = "nbpl_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbpl_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Where it signed in from, as the screens' server reported it.
    address: Mapped[str | None] = mapped_column(String(64), default=None)


# ---- Organizations -------------------------------------------------------------

COMPANY_STATUSES = ("active", "suspended")
UNIT_KINDS = ("department", "branch")


class Company(Base):
    __tablename__ = "nbpl_companies"
    __table_args__ = (_one_of("status", COMPANY_STATUSES, "nbpl_company_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    currency: Mapped[str] = mapped_column(String(3), default="PHP")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Manila")
    contact_email: Mapped[str | None] = mapped_column(String(254), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class OrgUnit(Base):
    """A department or a branch of one company."""

    __tablename__ = "nbpl_org_units"
    __table_args__ = (
        _one_of("kind", UNIT_KINDS, "nbpl_org_unit_kind"),
        UniqueConstraint("company_id", "kind", "name", name="nbpl_org_unit_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("nbpl_companies.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    # A branch's town or address; a department's floor. Free text.
    location: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---- Applications --------------------------------------------------------------

# What a Platform Admin can declare over whatever the health check says.
STATUS_OVERRIDES = ("degraded", "maintenance", "outage")
ENVIRONMENTS = ("production", "staging", "development")
INTEGRATION_STATUSES = ("operational", "degraded", "down", "unknown")


class Application(Base):
    __tablename__ = "nbpl_applications"
    __table_args__ = (
        CheckConstraint("status_override IS NULL OR status_override IN ('degraded', 'maintenance', 'outage')", name="nbpl_application_override"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # The app key the screens use (crm, inventory, platform...).
    key: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    # Where people open it, and where the platform asks whether it is up.
    app_url: Mapped[str | None] = mapped_column(String(500), default=None)
    health_url: Mapped[str | None] = mapped_column(String(500), default=None)
    # Its API, which other applications call when they're linked to it.
    api_url: Mapped[str | None] = mapped_column(String(500), default=None)
    version: Mapped[str | None] = mapped_column(String(40), default=None)
    # The key it connects to the platform with (PLATFORM_APP_KEY on its server):
    # only its hash is kept, and the last characters to tell keys apart.
    connect_key_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    connect_key_hint: Mapped[str | None] = mapped_column(String(12), default=None)
    connect_key_made_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # When it last asked for its links: how the platform knows it's connected.
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # The key it encrypts its own secrets with (each person's mailbox, its order
    # links), given with its links: made once, kept encrypted, the same through new connect keys.
    data_key: Mapped[str | None] = mapped_column(Text, default=None)
    # Retired applications stay for their history, out of the lists.
    is_active: Mapped[bool] = mapped_column(default=True)
    status_override: Mapped[str | None] = mapped_column(String(16), default=None)
    status_note: Mapped[str | None] = mapped_column(String(300), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Deployment(Base):
    __tablename__ = "nbpl_deployments"
    __table_args__ = (_one_of("environment", ENVIRONMENTS, "nbpl_deployment_environment"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(16), default="production")
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    recorded_by: Mapped[str] = mapped_column(String(254))


class Integration(Base):
    """Something an application depends on outside itself: a payment gateway,
    another app's API, a mail service."""

    __tablename__ = "nbpl_integrations"
    __table_args__ = (_one_of("status", INTEGRATION_STATUSES, "nbpl_integration_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # What it connects to, in words ("Supabase Postgres", "Inventory API").
    target: Mapped[str | None] = mapped_column(String(200), default=None)
    # When set, the platform checks it like an application; when not, its
    # status is whatever was last set by hand.
    health_url: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppLink(Base):
    """One application uses another (the CRM uses Inventory): the caller is
    given the other's address and a key, the other accepts that key. The key
    is kept encrypted (app/links.py); switching the link off takes it from both."""

    __tablename__ = "nbpl_app_links"
    __table_args__ = (UniqueConstraint("from_app_id", "to_app_id", name="nbpl_app_link_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    from_app_id: Mapped[str] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="CASCADE"), index=True)
    to_app_id: Mapped[str] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="CASCADE"), index=True)
    is_on: Mapped[bool] = mapped_column(default=True)
    secret: Mapped[str] = mapped_column(Text)
    made_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ServiceConnection(Base):
    """A company's details for an outside service (Zoho Books, Gmail...): which
    ones and what they need are in app/services.py. The secret ones are one
    encrypted JSON object; the applications that use the service are given them."""

    __tablename__ = "nbpl_service_connections"
    __table_args__ = (UniqueConstraint("company_id", "service", name="nbpl_service_connection_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("nbpl_companies.id", ondelete="CASCADE"), index=True)
    service: Mapped[str] = mapped_column(String(40))
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    secrets: Mapped[str | None] = mapped_column(Text, default=None)
    is_enabled: Mapped[bool] = mapped_column(default=False)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    check_ok: Mapped[bool | None] = mapped_column(default=None)
    check_message: Mapped[str | None] = mapped_column(String(300), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_users.id", ondelete="SET NULL"), default=None)


class CompanyApp(Base):
    """A company may use an application."""

    __tablename__ = "nbpl_company_apps"

    company_id: Mapped[str] = mapped_column(ForeignKey("nbpl_companies.id", ondelete="CASCADE"), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="CASCADE"), primary_key=True, index=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---- Platform users and their access -------------------------------------------

IDENTITY_STATUSES = ("active", "suspended")
REQUEST_STATUSES = ("pending", "approved", "declined")


class Identity(Base):
    """A person at a company: their standing there (title, whether they run it,
    the applications they have). Someone who works for two companies has a row
    at each, under the same email, and one password for both: they sign in
    once and switch between them (app/routers/identity.py)."""

    __tablename__ = "nbpl_identities"
    __table_args__ = (
        _one_of("status", IDENTITY_STATUSES, "nbpl_identity_status"),
        UniqueConstraint("company_id", "email", name="nbpl_identity_email"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("nbpl_companies.id", ondelete="RESTRICT"), index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), index=True)
    title: Mapped[str | None] = mapped_column(String(120), default=None)
    # Runs their own company: its people, its application access, its settings.
    is_company_admin: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Their Bishnoi One account's password: one sign-in for every application they
    # have (app/routers/identity.py). None until a Platform Admin sets a first one.
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class IdentitySession(Base):
    """One sign-in to a Bishnoi One account (not the console's staff sign-in). The
    browser or Bishnoi One.exe holds the token; only its hash is kept here."""

    __tablename__ = "nbpl_identity_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    identity_id: Mapped[str] = mapped_column(ForeignKey("nbpl_identities.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class IdentityApp(Base):
    """One person may use one application, with a role there."""

    __tablename__ = "nbpl_identity_apps"

    identity_id: Mapped[str] = mapped_column(ForeignKey("nbpl_identities.id", ondelete="CASCADE"), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="CASCADE"), primary_key=True, index=True)
    # The role's name in that application ("Salesperson", "Pharmacist").
    role: Mapped[str | None] = mapped_column(String(60), default=None)
    # Runs that one application for their company.
    is_app_admin: Mapped[bool] = mapped_column(default=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    granted_by: Mapped[str] = mapped_column(String(254))


class AccessRequest(Base):
    __tablename__ = "nbpl_access_requests"
    __table_args__ = (_one_of("status", REQUEST_STATUSES, "nbpl_access_request_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    identity_id: Mapped[str] = mapped_column(ForeignKey("nbpl_identities.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="CASCADE"))
    role: Mapped[str | None] = mapped_column(String(60), default=None)
    reason: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decided_by: Mapped[str | None] = mapped_column(String(254), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(500), default=None)


# ---- Support -------------------------------------------------------------------

TICKET_KINDS = ("complaint", "bug", "issue", "feature", "support")
SEVERITIES = ("critical", "high", "medium", "low")
# Reported -> Triaged -> Assigned -> Investigating -> Fix in development ->
# Testing -> Resolved -> Closed. A complaint or a question may skip steps.
TICKET_STATUSES = ("reported", "triaged", "assigned", "investigating", "fixing", "testing", "resolved", "closed")


class Ticket(Base):
    __tablename__ = "nbpl_tickets"
    __table_args__ = (
        _one_of("kind", TICKET_KINDS, "nbpl_ticket_kind"),
        _one_of("severity", SEVERITIES, "nbpl_ticket_severity"),
        _one_of("status", TICKET_STATUSES, "nbpl_ticket_status"),
        Index("ix_nbpl_tickets_open", "status", "kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # BUG-2026-00421: the kind, the year, and its place in that year.
    number: Mapped[str] = mapped_column(String(24), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="reported")
    company_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_companies.id", ondelete="SET NULL"), default=None, index=True)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="SET NULL"), default=None, index=True)
    identity_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_identities.id", ondelete="SET NULL"), default=None)
    # Who reported it, as they gave it: they may not be on the platform at all.
    reporter_name: Mapped[str | None] = mapped_column(String(120), default=None)
    reporter_email: Mapped[str | None] = mapped_column(String(254), default=None)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_users.id", ondelete="SET NULL"), default=None, index=True)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_incidents.id", ondelete="SET NULL"), default=None)
    affected_users: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class TicketNote(Base):
    """A note on a ticket, or a change of its status (then both are set)."""

    __tablename__ = "nbpl_ticket_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("nbpl_tickets.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_users.id", ondelete="SET NULL"), default=None)
    author: Mapped[str] = mapped_column(String(120))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    status_from: Mapped[str | None] = mapped_column(String(16), default=None)
    status_to: Mapped[str | None] = mapped_column(String(16), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---- Incidents -----------------------------------------------------------------

INCIDENT_KINDS = ("disruption", "application", "performance", "security")
INCIDENT_SEVERITIES = ("critical", "major", "minor")
INCIDENT_STATUSES = ("investigating", "identified", "monitoring", "resolved")


class Incident(Base):
    """Something happening now that stops people working, as opposed to a
    ticket, which is one person's report of something wrong."""

    __tablename__ = "nbpl_incidents"
    __table_args__ = (
        _one_of("kind", INCIDENT_KINDS, "nbpl_incident_kind"),
        _one_of("severity", INCIDENT_SEVERITIES, "nbpl_incident_severity"),
        _one_of("status", INCIDENT_STATUSES, "nbpl_incident_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(24), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16), default="disruption")
    severity: Mapped[str] = mapped_column(String(16), default="major")
    status: Mapped[str] = mapped_column(String(16), default="investigating", index=True)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="SET NULL"), default=None, index=True)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_users.id", ondelete="SET NULL"), default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by: Mapped[str] = mapped_column(String(254))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IncidentCompany(Base):
    """A company the incident reaches. None listed: everyone on the application."""

    __tablename__ = "nbpl_incident_companies"

    incident_id: Mapped[str] = mapped_column(ForeignKey("nbpl_incidents.id", ondelete="CASCADE"), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("nbpl_companies.id", ondelete="CASCADE"), primary_key=True, index=True)


class IncidentUpdate(Base):
    __tablename__ = "nbpl_incident_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(ForeignKey("nbpl_incidents.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---- Monitoring ----------------------------------------------------------------

HEALTH_STATUSES = ("operational", "degraded", "down")
CHECK_TARGETS = ("application", "integration", "database")


class HealthCheck(Base):
    """One look at whether something answers, and how fast."""

    __tablename__ = "nbpl_health_checks"
    __table_args__ = (
        _one_of("status", HEALTH_STATUSES, "nbpl_health_status"),
        _one_of("target_kind", CHECK_TARGETS, "nbpl_health_target"),
        Index("ix_nbpl_health_target", "target_kind", "target_id", "checked_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_kind: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16))
    ms: Mapped[int | None] = mapped_column(Integer, default=None)
    http_status: Mapped[int | None] = mapped_column(Integer, default=None)
    # Why it isn't operational, in words. Never an error's raw text.
    detail: Mapped[str | None] = mapped_column(String(300), default=None)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class TrafficMinute(Base):
    """The Platform API's own requests, one row per minute."""

    __tablename__ = "nbpl_traffic"

    minute: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    # 4xx: refused (a wrong password, a record out of reach). 5xx: failed.
    refused: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    total_ms: Mapped[int] = mapped_column(Integer, default=0)
    max_ms: Mapped[int] = mapped_column(Integer, default=0)


# ---- Activity & audit ----------------------------------------------------------

AUDIT_CATEGORIES = ("admin", "security", "support", "system")


class AuditEntry(Base):
    """Who did what, and when. Names the fields that changed, never their values."""

    __tablename__ = "nbpl_audit"
    __table_args__ = (_one_of("category", AUDIT_CATEGORIES, "nbpl_audit_category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_users.id", ondelete="SET NULL"), default=None, index=True)
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(60), index=True)
    category: Mapped[str] = mapped_column(String(16), default="admin", index=True)
    target_type: Mapped[str | None] = mapped_column(String(40), default=None)
    target_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    target: Mapped[str] = mapped_column(String(200), default="")
    fields: Mapped[list] = mapped_column(JSON, default=list)
    company_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    application_id: Mapped[str | None] = mapped_column(String(36), default=None)
    address: Mapped[str | None] = mapped_column(String(64), default=None)


# ---- Communications ------------------------------------------------------------

NOTICE_KINDS = ("announcement", "notification", "maintenance")
NOTICE_LEVELS = ("info", "warning", "critical")


class Announcement(Base):
    """Something the platform tells people. With no company or application set,
    it is for everyone."""

    __tablename__ = "nbpl_announcements"
    __table_args__ = (
        _one_of("kind", NOTICE_KINDS, "nbpl_announcement_kind"),
        _one_of("level", NOTICE_LEVELS, "nbpl_announcement_level"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16), default="announcement")
    level: Mapped[str] = mapped_column(String(16), default="info")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_companies.id", ondelete="CASCADE"), default=None)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("nbpl_applications.id", ondelete="CASCADE"), default=None)
    # Shown from starts_at until ends_at (a maintenance window, or open-ended).
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # A draft until published.
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by: Mapped[str] = mapped_column(String(254))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---- Settings ------------------------------------------------------------------


class PlatformSetting(Base):
    """One section of Settings, as JSON (see app/platform_settings.py)."""

    __tablename__ = "nbpl_settings"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(254), default=None)
