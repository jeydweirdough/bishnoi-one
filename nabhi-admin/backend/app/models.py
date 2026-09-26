"""This app's own accounts. Nobody signed in here exists in any other Nabhi app.

Every table's name starts with nbad_ (Admin), so it is plain which app a
table belongs to, whatever database it ends up in. Changes to them go through
a migration (migrations/versions)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Role(Base):
    __tablename__ = "nbad_roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    # Administrator: always every permission, can't be changed or deleted.
    is_system: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    grants: Mapped[list["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan", lazy="selectin")

    @property
    def permissions(self) -> set[str]:
        return {g.permission for g in self.grants}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            if other == "admin":
                return self.is_system or self.name == "Administrator"
            return self.name.lower() == other.lower()
        return super().__eq__(other)


class RolePermission(Base):
    __tablename__ = "nbad_role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("nbad_roles.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)

    role: Mapped[Role] = relationship(back_populates="grants")


class User(Base):
    __tablename__ = "nbad_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("nbad_roles.id"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    role: Mapped[Role] = relationship(lazy="joined")

    def __init__(self, **kwargs):
        role_val = kwargs.pop("role", None)
        if "role_id" not in kwargs:
            from app.permissions import ROLE_ADMIN_ID, ROLE_EXEC_ASST_ID
            if isinstance(role_val, str):
                kwargs["role_id"] = ROLE_ADMIN_ID if role_val == "admin" else ROLE_EXEC_ASST_ID
            elif isinstance(role_val, Role):
                kwargs["role"] = role_val
            else:
                kwargs["role_id"] = ROLE_EXEC_ASST_ID
        super().__init__(**kwargs)



class SignInSession(Base):
    """One sign-in. The browser holds the token; only its hash is kept here."""

    __tablename__ = "nbad_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("nbad_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class AuditEntry(Base):
    """The activity log: who changed what, and when."""

    __tablename__ = "nbad_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32), default=None)
    target_id: Mapped[str | None] = mapped_column(String(36), default=None)
    target: Mapped[str] = mapped_column(String(200), default="")
    fields: Mapped[list[str]] = mapped_column(JSON, default=list)



# --- Executive Office & Administration Tables ----------------------------------------


class ComplianceRecord(Base):
    """Corporate and regulatory registrations, permits, and accreditations (BOC, SEC, BIR, LGU, FDA)."""

    __tablename__ = "nbad_compliance_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))  # boc, lgu, sec, bir, fda, sanitary_fire, other
    agency: Mapped[str] = mapped_column(String(100))  # e.g. Bureau of Customs (BOC), LGU Makati, SEC, BIR, FDA
    reference_number: Mapped[str] = mapped_column(String(80))
    issuance_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expiration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # countdown target
    renewal_window_days: Mapped[int] = mapped_column(default=60)
    status: Mapped[str] = mapped_column(String(24), default="active")  # active, pending_renewal, under_review, expired
    responsible_person: Mapped[str | None] = mapped_column(String(120), default=None)
    estimated_cost: Mapped[float | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ImmigrationRecord(Base):
    """Expatriate, executive visas, Alien Certificate of Registration (ACR I-Card), DOLE AEP, and passports."""

    __tablename__ = "nbad_immigration_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    individual_name: Mapped[str] = mapped_column(String(120))
    designation: Mapped[str] = mapped_column(String(120))
    nationality: Mapped[str] = mapped_column(String(60))
    document_type: Mapped[str] = mapped_column(String(40))  # visa, acr_card, aep_permit, passport, exec_id
    document_number: Mapped[str] = mapped_column(String(80))
    issuance_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expiration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # countdown target
    renewal_lead_days: Mapped[int] = mapped_column(default=60)
    sponsoring_entity: Mapped[str | None] = mapped_column(String(120), default=None)
    status: Mapped[str] = mapped_column(String(24), default="valid")  # valid, expiring_soon, in_renewal, expired
    assigned_assistant: Mapped[str | None] = mapped_column(String(120), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CorporateDocument(Base):
    """Commercial contracts, corporate insurance policies (D&O, CGL, property), and board resolutions."""

    __tablename__ = "nbad_corporate_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))  # insurance, contract, nda, board_resolution, sla, legal_retainer
    counterparty: Mapped[str] = mapped_column(String(140))
    reference_number: Mapped[str | None] = mapped_column(String(80), default=None)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    auto_renews: Mapped[bool] = mapped_column(default=False)
    notice_period_days: Mapped[int] = mapped_column(default=30)
    custodian: Mapped[str | None] = mapped_column(String(120), default=None)
    status: Mapped[str] = mapped_column(String(24), default="active")  # active, in_review, renewed, terminated
    annual_value: Mapped[float | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PropertyRecord(Base):
    """Corporate facilities, office leases, pharma warehouses, depot facilities, and utilities."""

    __tablename__ = "nbad_properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(140))
    property_type: Mapped[str] = mapped_column(String(40))  # office, warehouse, depot, parking, expat_housing
    address: Mapped[str] = mapped_column(String(250))
    lessor_name: Mapped[str] = mapped_column(String(140))
    lessor_contact: Mapped[str | None] = mapped_column(String(140), default=None)
    lease_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    lease_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # countdown target
    notice_deadline_days: Mapped[int] = mapped_column(default=90)
    monthly_rent: Mapped[float | None] = mapped_column(default=None)
    escalation_rate_pct: Mapped[float | None] = mapped_column(default=None)
    security_deposit: Mapped[float | None] = mapped_column(default=None)
    utilities_info: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[str] = mapped_column(String(24), default="active")  # active, renewal_negotiation, expiring_soon, terminated
    assigned_manager: Mapped[str | None] = mapped_column(String(120), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Ticket(Base):
    """Office concerns, administrative service desk requests, facilities, and executive VIP logistics."""

    __tablename__ = "nbad_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_number: Mapped[str] = mapped_column(String(24), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))  # facilities, vip_logistics, supplies, it_security, boardroom, courier_dispatch, general
    priority: Mapped[str] = mapped_column(String(16), default="normal")  # urgent, high, normal, low
    status: Mapped[str] = mapped_column(String(24), default="open")  # open, in_progress, pending_vendor, resolved, closed
    requester_name: Mapped[str] = mapped_column(String(120))
    requester_email: Mapped[str | None] = mapped_column(String(254), default=None)
    executive_sponsor: Mapped[str | None] = mapped_column(String(120), default=None)
    assigned_to: Mapped[str | None] = mapped_column(String(120), default=None)
    sla_due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    description: Mapped[str] = mapped_column(String(1000))
    resolution_notes: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TicketUpdate(Base):
    """Updates and comments on office concern tickets."""

    __tablename__ = "nbad_ticket_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("nbad_tickets.id", ondelete="CASCADE"), index=True)
    author_name: Mapped[str] = mapped_column(String(120))
    author_email: Mapped[str | None] = mapped_column(String(254), default=None)
    update_type: Mapped[str] = mapped_column(String(24), default="comment")  # comment, status_change, resolution
    content: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    """Proactive expiration countdowns, renewal alerts, and milestone warnings."""

    __tablename__ = "nbad_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(32))  # permit, immigration, document, property, ticket
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warning")  # critical, urgent, warning, info
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(String(500))
    days_remaining: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_read: Mapped[bool] = mapped_column(default=False)
    is_acknowledged: Mapped[bool] = mapped_column(default=False)
    is_resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

