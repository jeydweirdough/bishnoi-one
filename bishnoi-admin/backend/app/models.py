"""This app's own accounts. Nobody signed in here exists in any other Bishnoi One app.

Every table's name starts with nbad_ (Admin), so it is plain which app a
table belongs to, whatever database it ends up in. Changes to them go through
a migration (migrations/versions)."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, FetchedValue, ForeignKey, Index, Integer, LargeBinary, String
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
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbad_users_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    # Their name in parts, as they keep it on their profile; full_name is made
    # from these (app/routers/profile.py), and is what everything else reads.
    first_name: Mapped[str | None] = mapped_column(String(60), default=None)
    middle_initial: Mapped[str | None] = mapped_column(String(4), default=None)
    last_name: Mapped[str | None] = mapped_column(String(60), default=None)
    suffix: Mapped[str | None] = mapped_column(String(10), default=None)
    gender: Mapped[str | None] = mapped_column(String(8), default=None)
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    birthday: Mapped[date | None] = mapped_column(Date, default=None)
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("nbad_roles.id"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Their Bishnoi One account on the platform, once they have signed in with it (app/platform_pass.py).
    platform_identity_id: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)

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


class PlatformPass(Base):
    """A pass from the platform already taken: each one works once. Kept until it would have expired."""

    __tablename__ = "nbad_platform_passes"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


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
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbad_compliance_records_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
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
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbad_immigration_records_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
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
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbad_corporate_documents_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
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
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbad_properties_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
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


# --- Fleet, travel and devices (the executive assistant's trackers) ---------------
# What the office looks after day to day, moved in from the JASMINE TASKS
# workbook (2026-10-08): the company's vehicles and their renewals, the sales
# team's fuel cards, doctors' hotel and flight sponsorships, and the laptops,
# phones and SIMs handed out.

VEHICLE_KINDS = ("car", "motorcycle")


def guess_vehicle_kind(name: str | None, plate: str | None) -> str:
    """A motorcycle by its plate (Philippine motorcycle plates start with
    digits: 707XEZ, 133606; a car's with letters: NKT 4569) or its name; else a car."""
    plate = (plate or "").strip()
    if plate[:1].isdigit():
        return "motorcycle"
    words = (name or "").upper()
    return "motorcycle" if any(w in words for w in ("MOTORCYCLE", "MOTORBIKE", "SCOOTER")) else "car"


class Vehicle(Base):
    """A company car or motorcycle: its registration, insurance and maintenance falling due."""

    __tablename__ = "nbad_vehicles"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (Index("nbad_vehicles_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    name: Mapped[str] = mapped_column(String(140))  # "Ford Ranger AT"
    kind: Mapped[str] = mapped_column(String(12), default="car")  # car or motorcycle: its icon
    plate: Mapped[str | None] = mapped_column(String(20), default=None, index=True)
    year_model: Mapped[int | None] = mapped_column(Integer, default=None)
    color: Mapped[str | None] = mapped_column(String(60), default=None)
    owner_name: Mapped[str | None] = mapped_column(String(200), default=None)  # registered owner, and who has it
    registration_due: Mapped[date | None] = mapped_column(Date, default=None)
    insurance_due: Mapped[date | None] = mapped_column(Date, default=None)
    pms_due: Mapped[date | None] = mapped_column(Date, default=None)  # preventive maintenance
    fleet_card: Mapped[str | None] = mapped_column(String(120), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FleetCard(Base):
    """A fuel card given to a salesperson: their allowance, the car it's for, and whether it works."""

    __tablename__ = "nbad_fleet_cards"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint("status IN ('processing', 'handed_over', 'with_hr', 'returned')", name="nbad_fleet_card_status"),
        CheckConstraint("card_state IN ('active', 'blocked')", name="nbad_fleet_card_state"),
        Index("nbad_fleet_cards_no", "no", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    requested_on: Mapped[date | None] = mapped_column(Date, default=None)
    holder_name: Mapped[str] = mapped_column(String(140), index=True)
    company_name: Mapped[str | None] = mapped_column(String(140), default=None)
    monthly_allowance: Mapped[float | None] = mapped_column(default=None)  # pesos a month
    allowance_note: Mapped[str | None] = mapped_column(String(80), default=None)  # when it's not pesos: "200 liters a month"
    fuel_type: Mapped[str | None] = mapped_column(String(60), default=None)
    plate: Mapped[str | None] = mapped_column(String(20), default=None)
    conduction_sticker: Mapped[str | None] = mapped_column(String(30), default=None)  # a new car's, before its plate
    vehicle_unit: Mapped[str | None] = mapped_column(String(140), default=None)
    status: Mapped[str] = mapped_column(String(16), default="processing")
    card_state: Mapped[str] = mapped_column(String(10), default="active")
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TravelSponsorship(Base):
    """A doctor's hotel stay or flight the company pays for, asked for by a rep."""

    __tablename__ = "nbad_travel_sponsorships"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint("kind IN ('hotel', 'flight')", name="nbad_travel_kind"),
        CheckConstraint("status IN ('for_approval', 'for_processing', 'approved', 'booked', 'cancelled')", name="nbad_travel_status"),
        Index("nbad_travel_sponsorships_no", "no", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    requested_on: Mapped[date | None] = mapped_column(Date, default=None)
    rep_name: Mapped[str] = mapped_column(String(140), index=True)  # the medical sales associate who asked
    doctor_name: Mapped[str] = mapped_column(String(140), index=True)
    doctor_birthdate: Mapped[date | None] = mapped_column(Date, default=None)  # airlines ask for it
    kind: Mapped[str] = mapped_column(String(10), default="hotel")
    travel_dates: Mapped[str | None] = mapped_column(String(140), default=None)  # as agreed: "November 25-27, 2026"
    starts_on: Mapped[date | None] = mapped_column(Date, default=None)  # the first day, for the countdown
    hotel_or_flight: Mapped[str | None] = mapped_column(String(200), default=None)
    status: Mapped[str] = mapped_column(String(16), default="for_approval")
    approved_on: Mapped[date | None] = mapped_column(Date, default=None)
    next_step: Mapped[str | None] = mapped_column(String(200), default=None)  # "For confirmation", "For payment"
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DeviceIssue(Base):
    """A laptop, phone or SIM handed to someone, and who signed for it."""

    __tablename__ = "nbad_device_issues"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (CheckConstraint("condition IN ('brand_new', 'repaired', 'used')", name="nbad_device_condition"), Index("nbad_device_issues_no", "no", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    issued_on: Mapped[date | None] = mapped_column(Date, default=None)
    issued_to: Mapped[str] = mapped_column(String(200), index=True)
    laptop: Mapped[str | None] = mapped_column(String(140), default=None)
    phone: Mapped[str | None] = mapped_column(String(140), default=None)
    sim: Mapped[str | None] = mapped_column(String(60), default=None)
    condition: Mapped[str] = mapped_column(String(10), default="brand_new")
    signed_by: Mapped[str | None] = mapped_column(String(140), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RecordEvent(Base):
    """What happened to a vehicle, fuel card, sponsorship or device issue, for
    its history: added, changed, renewed, PMS done, booked, blocked, a note."""

    __tablename__ = "nbad_record_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_type: Mapped[str] = mapped_column(String(20), index=True)  # vehicles, fleet-cards, travel, devices
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # added, changed, registration_renewed, note...
    text: Mapped[str] = mapped_column(String(500))
    by_name: Mapped[str | None] = mapped_column(String(140), default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class StoredFile(Base):
    """An uploaded file (a promotional material's design), kept in the database
    itself: a server without a lasting disk (Vercel) keeps it all the same, and
    it is backed up with everything else."""

    __tablename__ = "nbad_stored_files"

    ref: Mapped[str] = mapped_column(String(32), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromoMaterial(Base):
    """A promotional material (a leaflet, a poster, a giveaway): designed by the
    marketing assistant, approved by the pharmacist in Pharmacy, produced by the
    executive office, and given out to the CRM's teams once their manager approves.

    status: draft -> pharmacy_review -> approved (or returned for changes, or
    rejected) -> in_production -> available; retired when no longer given out.
    stock is what has been received from production less what has been given out."""

    __tablename__ = "nbad_promo_materials"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'pharmacy_review', 'returned', 'rejected', 'approved', 'in_production', 'available', 'retired')", name="nbad_promo_status"),
        Index("nbad_promo_materials_no", "no", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Its number, from 40000001 up (app/numbering.py): for paging and lookups; id stays the key.
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    title: Mapped[str] = mapped_column(String(160), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # Leaflet, Poster, Standee, Giveaway...
    product: Mapped[str | None] = mapped_column(String(160), default=None)  # what it promotes
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
    quantity: Mapped[int | None] = mapped_column(Integer, default=None)  # how many are planned
    specs: Mapped[str | None] = mapped_column(String(300), default=None)  # size, paper, colours
    needed_by: Mapped[date | None] = mapped_column(Date, default=None)
    budget: Mapped[float | None] = mapped_column(default=None)  # pesos, the whole run
    status: Mapped[str] = mapped_column(String(20), default="draft")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    created_by_name: Mapped[str | None] = mapped_column(String(140), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    versions: Mapped[list["PromoVersion"]] = relationship(back_populates="material", cascade="all, delete-orphan", order_by="PromoVersion.number", lazy="selectin")


class PromoVersion(Base):
    """One design of a material, as sent to the pharmacist. A design returned
    for changes is followed by a new version; each keeps its file and the
    pharmacist's comments.

    review: draft (not sent), waiting, approved, returned or rejected; the last
    answer from Pharmacy is kept with when it was had."""

    __tablename__ = "nbad_promo_versions"
    __table_args__ = (CheckConstraint("review IN ('draft', 'waiting', 'approved', 'returned', 'rejected')", name="nbad_promo_version_review"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    material_id: Mapped[str] = mapped_column(ForeignKey("nbad_promo_materials.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)  # 1, 2, 3...
    file_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    file_name: Mapped[str | None] = mapped_column(String(200), default=None)
    notes: Mapped[str | None] = mapped_column(String(1000), default=None)  # what changed, for the pharmacist
    review: Mapped[str] = mapped_column(String(10), default="draft")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    sent_by_name: Mapped[str | None] = mapped_column(String(140), default=None)
    pharmacy_number: Mapped[str | None] = mapped_column(String(40), default=None)  # Pharmacy's reference
    comments: Mapped[str | None] = mapped_column(String(2000), default=None)  # the pharmacist's
    reviewed_by: Mapped[str | None] = mapped_column(String(140), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    sync_error: Mapped[str | None] = mapped_column(String(300), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    material: Mapped[PromoMaterial] = relationship(back_populates="versions")


class PromoProduction(Base):
    """A print run or order of a material: ordered, then received into stock (or cancelled)."""

    __tablename__ = "nbad_promo_productions"
    __table_args__ = (CheckConstraint("status IN ('ordered', 'received', 'cancelled')", name="nbad_promo_production_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    material_id: Mapped[str] = mapped_column(ForeignKey("nbad_promo_materials.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)  # the approved design produced
    quantity: Mapped[int] = mapped_column(Integer)
    supplier: Mapped[str | None] = mapped_column(String(160), default=None)  # the printer or maker
    cost: Mapped[float | None] = mapped_column(default=None)  # pesos, the whole run
    ordered_on: Mapped[date | None] = mapped_column(Date, default=None)
    expected_on: Mapped[date | None] = mapped_column(Date, default=None)
    received_on: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(String(10), default="ordered")
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    by_name: Mapped[str | None] = mapped_column(String(140), default=None)
    # A photo or scan of the delivery, as proof it was received (nbad_stored_files).
    proof_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    proof_name: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromoDistribution(Base):
    """Some of a material given to a CRM team (or one person in it), once the
    team's manager approves in the CRM. The CRM's last answer is kept with when
    it was had.

    status: for_approval -> approved (or rejected) -> distributed; cancelled
    while not yet given out."""

    __tablename__ = "nbad_promo_distributions"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint("status IN ('for_approval', 'approved', 'rejected', 'distributed', 'cancelled')", name="nbad_promo_distribution_status"),
        Index("nbad_promo_distributions_no", "no", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    no: Mapped[int | None] = mapped_column(Integer, server_default=FetchedValue())
    material_id: Mapped[str] = mapped_column(ForeignKey("nbad_promo_materials.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[str] = mapped_column(String(36))  # the CRM's
    team_name: Mapped[str] = mapped_column(String(140))
    recipient_id: Mapped[str | None] = mapped_column(String(36), default=None)  # a person in that team, the CRM's
    recipient_name: Mapped[str | None] = mapped_column(String(140), default=None)
    quantity: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[str] = mapped_column(String(12), default="for_approval")
    requested_by_name: Mapped[str | None] = mapped_column(String(140), default=None)
    manager_name: Mapped[str | None] = mapped_column(String(140), default=None)  # who decided, in the CRM
    decision_note: Mapped[str | None] = mapped_column(String(500), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    distributed_on: Mapped[date | None] = mapped_column(Date, default=None)
    # A photo of the hand-over or the signed receipt, as proof it was given out.
    proof_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    proof_name: Mapped[str | None] = mapped_column(String(200), default=None)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    sync_error: Mapped[str | None] = mapped_column(String(300), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# Numbers on SQLite as records are saved (on Postgres the database gives them).
from app.numbering import numbered  # noqa: E402  (after the models it names)

numbered(User, ComplianceRecord, ImmigrationRecord, CorporateDocument, PropertyRecord, Vehicle, FleetCard, TravelSponsorship, DeviceIssue, PromoMaterial, PromoDistribution)
