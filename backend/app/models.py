"""Sales' tables. Changes to them go through a migration (migrations/versions).

Accounts here are Sales' own: nobody signed in here exists in any other Orbit app.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    # Switched off: kept for its history, but nobody new is put in it.
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (CheckConstraint("scope IN ('own', 'team', 'all')", name="role_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), default=None)
    # Whose records its permissions reach (app/permissions.py).
    scope: Mapped[str] = mapped_column(String(8), default="own")
    # Administrator: always every permission, can't be changed or deleted.
    is_system: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    grants: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def permissions(self) -> set[str]:
        return {g.permission for g in self.grants}


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)

    role: Mapped[Role] = relationship(back_populates="grants")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), index=True, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Every session started before this ends (see deps.current_user).
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    role: Mapped[Role] = relationship(lazy="joined")
    team: Mapped[Team | None] = relationship(lazy="joined")


class SignInSession(Base):
    """One sign-in. The browser holds the token; only its hash is kept here."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class AuditEntry(Base):
    """Who changed what, and when. Names the fields that changed, never their
    values, so it can be shown to admins without leaking what something was."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    # Kept as written at the time, so the log still reads after a rename.
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32), default=None)
    target_id: Mapped[str | None] = mapped_column(String(36), default=None)
    target: Mapped[str] = mapped_column(String(200), default="")
    fields: Mapped[list[str]] = mapped_column(JSON, default=list)


# --- customers and what's done with them --------------------------------------------
#
# Every record has an owner (a person here) and the owner's team, which is what
# a role's scope reads (app/scope.py): own records, the team's, or all of them.


class Owned:
    """Who a record belongs to. `team_id` is the owner's team when it was last
    given to them, so moving someone to another team doesn't move their records."""

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), index=True, default=None)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


COMPANY_STATUSES = ("prospect", "customer", "partner", "inactive")


class Company(Owned, Base):
    __tablename__ = "companies"
    __table_args__ = (CheckConstraint("status IN ('prospect', 'customer', 'partner', 'inactive')", name="company_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(16), default="prospect")
    industry: Mapped[str | None] = mapped_column(String(80), default=None)
    website: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    city: Mapped[str | None] = mapped_column(String(80), default=None)
    country: Mapped[str | None] = mapped_column(String(80), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    owner: Mapped[User] = relationship(foreign_keys="Company.owner_id", lazy="joined")
    team: Mapped[Team | None] = relationship(lazy="joined")


class Contact(Owned, Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True, default=None)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80), default=None)
    job_title: Mapped[str | None] = mapped_column(String(120), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    mobile: Mapped[str | None] = mapped_column(String(40), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    company: Mapped[Company | None] = relationship(lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys="Contact.owner_id", lazy="joined")
    team: Mapped[Team | None] = relationship(lazy="joined")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() if self.last_name else self.first_name


ACTIVITY_KINDS = ("call", "meeting", "email", "note", "task")
# Kinds that are planned first and done later; the rest are logged once they've happened.
PLANNED_KINDS = ("meeting", "task")


class Activity(Owned, Base):
    """A call, meeting, email, note or task, about a company and/or a contact.

    `at` is when it happened (call, email, note) or when it's due (meeting,
    task). A meeting or task is open until `done_at` is set; the others are done
    when logged. The owner is who did it, or who it's assigned to."""

    __tablename__ = "activities"
    __table_args__ = (CheckConstraint("kind IN ('call', 'meeting', 'email', 'note', 'task')", name="activity_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(8), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, default=None)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), index=True, default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, default=None)
    # Calls and meetings: how long, in minutes. Calls and emails: which way.
    duration_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    direction: Mapped[str | None] = mapped_column(String(8), default=None)

    company: Mapped[Company | None] = relationship(lazy="joined")
    contact: Mapped[Contact | None] = relationship(lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys="Activity.owner_id", lazy="joined")

