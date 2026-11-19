"""The platform's records: companies and their departments and branches,
applications, platform users and their access, support tickets, incidents,
health checks, traffic, the audit log, announcements and settings.

The application registry starts with the apps in this repo, at their local
addresses; change them under Applications once they run anywhere else.

Revision ID: 0002
Revises: 0001
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _at(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _fk(name: str, table: str, ondelete: str, nullable: bool = False, primary_key: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id", ondelete=ondelete), nullable=nullable, primary_key=primary_key)


# key, name, what it is, screens' port, API's port
APPS = (
    ("platform", "Nabhi Platform", "This console: the companies, people and applications on Nabhi, and what is going wrong.", 4305, 8305),
    ("crm", "CRM", "Customers, and everything that happens with them.", 4302, 8302),
    ("inventory", "Inventory", "What the company sells, and what it costs.", 4304, 8304),
    ("pharmacy", "Pharmacy Management", "Prescriptions checked, and batches tracked.", 4307, 8307),
    ("exec", "Executive Admin", "Running one company.", 4300, 8300),
    ("finance", "Finance", "The money side of a quote.", 4303, 8303),
    ("inlicensing", "In-Licensing", "Products being taken on from a principal.", 4306, 8306),
    ("regulatory", "Regulatory Affairs", "Keeping every product legal to sell.", 4308, 8308),
)


def upgrade() -> None:
    op.create_table(
        "nbpl_companies",
        _id(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(40), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("contact_email", sa.String(254), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _at("created_at"),
        _at("suspended_at", nullable=True),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="nbpl_company_status"),
    )
    op.create_table(
        "nbpl_org_units",
        _id(),
        _fk("company_id", "nbpl_companies", "CASCADE"),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        _at("created_at"),
        sa.CheckConstraint("kind IN ('department', 'branch')", name="nbpl_org_unit_kind"),
        sa.UniqueConstraint("company_id", "kind", "name", name="nbpl_org_unit_name"),
    )
    op.create_index("ix_nbpl_org_units_company_id", "nbpl_org_units", ["company_id"])

    applications = op.create_table(
        "nbpl_applications",
        _id(),
        sa.Column("key", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("app_url", sa.String(500), nullable=True),
        sa.Column("health_url", sa.String(500), nullable=True),
        sa.Column("version", sa.String(40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("status_override", sa.String(16), nullable=True),
        sa.Column("status_note", sa.String(300), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        _at("created_at"),
        sa.CheckConstraint(
            "status_override IS NULL OR status_override IN ('degraded', 'maintenance', 'outage')", name="nbpl_application_override"
        ),
    )
    op.create_table(
        "nbpl_deployments",
        _id(),
        _fk("application_id", "nbpl_applications", "CASCADE"),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _at("deployed_at"),
        sa.Column("recorded_by", sa.String(254), nullable=False),
        sa.CheckConstraint("environment IN ('production', 'staging', 'development')", name="nbpl_deployment_environment"),
    )
    op.create_index("ix_nbpl_deployments_application_id", "nbpl_deployments", ["application_id"])
    op.create_table(
        "nbpl_integrations",
        _id(),
        _fk("application_id", "nbpl_applications", "CASCADE"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target", sa.String(200), nullable=True),
        sa.Column("health_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _at("created_at"),
        sa.CheckConstraint("status IN ('operational', 'degraded', 'down', 'unknown')", name="nbpl_integration_status"),
    )
    op.create_index("ix_nbpl_integrations_application_id", "nbpl_integrations", ["application_id"])
    op.create_table(
        "nbpl_company_apps",
        _fk("company_id", "nbpl_companies", "CASCADE", primary_key=True),
        _fk("application_id", "nbpl_applications", "CASCADE", primary_key=True),
        _at("granted_at"),
    )
    op.create_index("ix_nbpl_company_apps_application_id", "nbpl_company_apps", ["application_id"])

    op.create_table(
        "nbpl_identities",
        _id(),
        _fk("company_id", "nbpl_companies", "RESTRICT"),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("is_company_admin", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        _at("created_at"),
        _at("last_active_at", nullable=True),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="nbpl_identity_status"),
    )
    op.create_index("ix_nbpl_identities_company_id", "nbpl_identities", ["company_id"])
    op.create_table(
        "nbpl_identity_apps",
        _fk("identity_id", "nbpl_identities", "CASCADE", primary_key=True),
        _fk("application_id", "nbpl_applications", "CASCADE", primary_key=True),
        sa.Column("role", sa.String(60), nullable=True),
        sa.Column("is_app_admin", sa.Boolean(), nullable=False),
        _at("granted_at"),
        sa.Column("granted_by", sa.String(254), nullable=False),
    )
    op.create_index("ix_nbpl_identity_apps_application_id", "nbpl_identity_apps", ["application_id"])
    op.create_table(
        "nbpl_access_requests",
        _id(),
        _fk("identity_id", "nbpl_identities", "CASCADE"),
        _fk("application_id", "nbpl_applications", "CASCADE"),
        sa.Column("role", sa.String(60), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        _at("created_at"),
        _at("decided_at", nullable=True),
        sa.Column("decided_by", sa.String(254), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'declined')", name="nbpl_access_request_status"),
    )
    op.create_index("ix_nbpl_access_requests_identity_id", "nbpl_access_requests", ["identity_id"])
    op.create_index("ix_nbpl_access_requests_status", "nbpl_access_requests", ["status"])

    # Before tickets, which may belong to one.
    op.create_table(
        "nbpl_incidents",
        _id(),
        sa.Column("number", sa.String(24), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        _fk("application_id", "nbpl_applications", "SET NULL", nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        _fk("lead_id", "nbpl_users", "SET NULL", nullable=True),
        _at("started_at"),
        _at("resolved_at", nullable=True),
        sa.Column("created_by", sa.String(254), nullable=False),
        _at("created_at"),
        sa.CheckConstraint("kind IN ('disruption', 'application', 'performance', 'security')", name="nbpl_incident_kind"),
        sa.CheckConstraint("severity IN ('critical', 'major', 'minor')", name="nbpl_incident_severity"),
        sa.CheckConstraint("status IN ('investigating', 'identified', 'monitoring', 'resolved')", name="nbpl_incident_status"),
    )
    op.create_index("ix_nbpl_incidents_status", "nbpl_incidents", ["status"])
    op.create_index("ix_nbpl_incidents_application_id", "nbpl_incidents", ["application_id"])
    op.create_table(
        "nbpl_incident_companies",
        _fk("incident_id", "nbpl_incidents", "CASCADE", primary_key=True),
        _fk("company_id", "nbpl_companies", "CASCADE", primary_key=True),
    )
    op.create_index("ix_nbpl_incident_companies_company_id", "nbpl_incident_companies", ["company_id"])
    op.create_table(
        "nbpl_incident_updates",
        _id(),
        _fk("incident_id", "nbpl_incidents", "CASCADE"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author", sa.String(120), nullable=False),
        _at("created_at"),
    )
    op.create_index("ix_nbpl_incident_updates_incident_id", "nbpl_incident_updates", ["incident_id"])

    op.create_table(
        "nbpl_tickets",
        _id(),
        sa.Column("number", sa.String(24), nullable=False, unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        _fk("company_id", "nbpl_companies", "SET NULL", nullable=True),
        _fk("application_id", "nbpl_applications", "SET NULL", nullable=True),
        _fk("identity_id", "nbpl_identities", "SET NULL", nullable=True),
        sa.Column("reporter_name", sa.String(120), nullable=True),
        sa.Column("reporter_email", sa.String(254), nullable=True),
        _fk("assignee_id", "nbpl_users", "SET NULL", nullable=True),
        _fk("incident_id", "nbpl_incidents", "SET NULL", nullable=True),
        sa.Column("affected_users", sa.Integer(), nullable=True),
        _at("created_at"),
        _at("updated_at"),
        _at("resolved_at", nullable=True),
        _at("closed_at", nullable=True),
        sa.CheckConstraint("kind IN ('complaint', 'bug', 'issue', 'feature', 'support')", name="nbpl_ticket_kind"),
        sa.CheckConstraint("severity IN ('critical', 'high', 'medium', 'low')", name="nbpl_ticket_severity"),
        sa.CheckConstraint(
            "status IN ('reported', 'triaged', 'assigned', 'investigating', 'fixing', 'testing', 'resolved', 'closed')",
            name="nbpl_ticket_status",
        ),
    )
    op.create_index("ix_nbpl_tickets_open", "nbpl_tickets", ["status", "kind"])
    op.create_index("ix_nbpl_tickets_company_id", "nbpl_tickets", ["company_id"])
    op.create_index("ix_nbpl_tickets_application_id", "nbpl_tickets", ["application_id"])
    op.create_index("ix_nbpl_tickets_assignee_id", "nbpl_tickets", ["assignee_id"])
    op.create_table(
        "nbpl_ticket_notes",
        _id(),
        _fk("ticket_id", "nbpl_tickets", "CASCADE"),
        _fk("author_id", "nbpl_users", "SET NULL", nullable=True),
        sa.Column("author", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status_from", sa.String(16), nullable=True),
        sa.Column("status_to", sa.String(16), nullable=True),
        _at("created_at"),
    )
    op.create_index("ix_nbpl_ticket_notes_ticket_id", "nbpl_ticket_notes", ["ticket_id"])

    op.create_table(
        "nbpl_health_checks",
        _id(),
        sa.Column("target_kind", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("ms", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("detail", sa.String(300), nullable=True),
        _at("checked_at"),
        sa.CheckConstraint("status IN ('operational', 'degraded', 'down')", name="nbpl_health_status"),
        sa.CheckConstraint("target_kind IN ('application', 'integration', 'database')", name="nbpl_health_target"),
    )
    op.create_index("ix_nbpl_health_target", "nbpl_health_checks", ["target_kind", "target_id", "checked_at"])
    op.create_index("ix_nbpl_health_checks_checked_at", "nbpl_health_checks", ["checked_at"])
    op.create_table(
        "nbpl_traffic",
        sa.Column("minute", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("refused", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("total_ms", sa.Integer(), nullable=False),
        sa.Column("max_ms", sa.Integer(), nullable=False),
    )

    op.create_table(
        "nbpl_audit",
        _id(),
        _at("created_at"),
        _fk("actor_id", "nbpl_users", "SET NULL", nullable=True),
        sa.Column("actor", sa.String(254), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=True),
        sa.Column("target_id", sa.String(36), nullable=True),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=True),
        sa.Column("application_id", sa.String(36), nullable=True),
        sa.Column("address", sa.String(64), nullable=True),
        sa.CheckConstraint("category IN ('admin', 'security', 'support', 'system')", name="nbpl_audit_category"),
    )
    for column in ("created_at", "actor_id", "action", "category", "target_id", "company_id"):
        op.create_index(f"ix_nbpl_audit_{column}", "nbpl_audit", [column])

    op.create_table(
        "nbpl_announcements",
        _id(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        _fk("company_id", "nbpl_companies", "CASCADE", nullable=True),
        _fk("application_id", "nbpl_applications", "CASCADE", nullable=True),
        _at("starts_at"),
        _at("ends_at", nullable=True),
        _at("published_at", nullable=True),
        sa.Column("created_by", sa.String(254), nullable=False),
        _at("created_at"),
        _at("updated_at"),
        sa.CheckConstraint("kind IN ('announcement', 'notification', 'maintenance')", name="nbpl_announcement_kind"),
        sa.CheckConstraint("level IN ('info', 'warning', 'critical')", name="nbpl_announcement_level"),
    )
    op.create_table(
        "nbpl_settings",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        _at("updated_at"),
        sa.Column("updated_by", sa.String(254), nullable=True),
    )

    now = datetime.now(UTC)
    op.bulk_insert(
        applications,
        [
            {
                "id": str(uuid.uuid4()),
                "key": key,
                "name": name,
                "description": what,
                "app_url": f"http://localhost:{screens}",
                "health_url": f"http://127.0.0.1:{api}/health",
                "version": "0.1.0",
                "is_active": True,
                "status_override": None,
                "status_note": None,
                "sort_order": order,
                "created_at": now,
            }
            for order, (key, name, what, screens, api) in enumerate(APPS)
        ],
    )


def downgrade() -> None:
    for table in (
        "nbpl_settings",
        "nbpl_announcements",
        "nbpl_audit",
        "nbpl_traffic",
        "nbpl_health_checks",
        "nbpl_ticket_notes",
        "nbpl_tickets",
        "nbpl_incident_updates",
        "nbpl_incident_companies",
        "nbpl_incidents",
        "nbpl_access_requests",
        "nbpl_identity_apps",
        "nbpl_identities",
        "nbpl_company_apps",
        "nbpl_integrations",
        "nbpl_deployments",
        "nbpl_applications",
        "nbpl_org_units",
        "nbpl_companies",
    ):
        op.drop_table(table)
