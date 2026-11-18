"""Approval slips (Step 4C, owner-approved 2026-11-18): one request that passes up the chain, like a routing slip.

A slip has a number (AR-000001, per company), what is asked (an app's record: a sales order), its attachments (the
quote, the Rx check, a guarantee letter, photos and documents added to it) and its steps, in order. Each step is
signed, or the slip is returned with a note. It prints as an official document with the company letterhead and
each signer's signature.

How a slip moves:

    an app sends approval.requested (business event, any app)  ──▶  open(): the slip and its steps
    the step's approver signs                                   ──▶  the next step waits; the last signature approves
    any step's approver returns it, with a note                 ──▶  returned: the requester changes and sends again
                                                                     (a new slip, linked to the returned one)
    approved or returned                                        ──▶  approval.decided goes to the app (only it)
    the app decides it another way (an administrator, a cancel) ──▶  approval.withdrawn: the slip is cancelled

Steps (chain_for): the requester's managers on the org chart, nearest first (the heads of their unit and of each unit
above, then who they report to by link: the same list the chart event sends, without watchers, who see but don't
approve), at most MAX_MANAGERS of them (coach, then mentor). Nobody on the chart: one group step, anyone whose role
holds the app's approve permission (sales orders: "Sales approver", Inventory sales.approve). An app may add group
steps of its own after the chain (`groupSteps`), e.g. Finance; sales orders add none today (see sales_order_steps).

Who may act on the step that waits: its approver; for a group step, anyone holding its permission; and the company's
administrators on any step (kept as acted_as "administrator"). Never the requester on their own request, whoever
they are.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.platform import unit_heads
from modules.platform.accounts import account_of, runs_company
from modules.platform.models import (AccessRole, AccessRolePermission, Application, Approval, ApprovalAttachment, ApprovalStep, Company,
                                     IdentityApp, Identity, MembershipUnit, Unit)

MAX_MANAGERS = 2
# What each kind's group step is, when the requester has nobody above them on the chart.
FALLBACK = {("inventory", "sales_order"): ("Sales approver", "inventory", "sales.approve"),
            ("crm", "price_change"): ("Price approver", "crm", "products.approve")}
FILE_TYPES = {b"%PDF": "application/pdf", b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg"}
MAX_FILE_BYTES, MAX_FILES = 5_000_000, 20


class Refused(Exception):
    """Why this person can't do that to this slip, in plain words."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def now() -> datetime:
    return datetime.now(UTC)


def _text(value, size: int) -> str | None:
    text = str(value or "").strip()
    return text[:size] or None


# ---- who ------------------------------------------------------------------------------------


def person_of(db: Session, company_id: str, identity_id: str | None, email: str | None) -> Identity | None:
    """The company's employee by their membership id, else by email; never an operator's let-in membership."""
    if identity_id:
        found = db.get(Identity, str(identity_id))
        if found is not None and found.company_id == company_id and not found.via_operator:
            return found
    if email:
        return db.scalar(select(Identity).where(Identity.company_id == company_id, func.lower(Identity.email) == str(email).strip().lower(),
                                                Identity.via_operator.is_(False)).limit(1))
    return None


def managers_chain(db: Session, person: Identity) -> list[Identity]:
    """Their managers on the chart, nearest first (heads up the units, then the reports-to link)."""
    units = {u.id: u for u in db.scalars(select(Unit).where(Unit.company_id == person.company_id))}
    heads = unit_heads.heads_by_unit(db, person.company_id)
    others = list(db.scalars(select(MembershipUnit.unit_id).where(MembershipUnit.membership_id == person.id)))
    ids = {i for hs in heads.values() for i in hs} | {person.reports_to_id}
    people = {i.id: i for i in db.scalars(select(Identity).where(Identity.id.in_([x for x in ids if x])))}
    emails = {i: p.email.lower() for i, p in people.items()}
    by_email = {p.email.lower(): p for p in people.values()}
    out = []
    for email in unit_heads.managers_of(units, heads, emails, person, others):
        p = by_email.get(email)
        if p is not None and p.status == "active" and p.deleted_at is None and p.id != person.id:
            out.append(p)
    return out


def role_name(db: Session, person: Identity) -> str | None:
    role = db.get(AccessRole, person.access_role_id) if person.access_role_id else None
    return role.name if role else None


def holds(db: Session, person: Identity, app_key: str, permission: str) -> bool:
    """Whether their role in that app holds the permission (or is full access), and they have the app."""
    app = db.scalar(select(Application).where(Application.key == app_key))
    if app is None or person.status != "active" or person.deleted_at is not None:
        return False
    grant = db.get(IdentityApp, (person.id, app.id))
    if grant is None:
        return False
    role_id = grant.access_role_id or person.access_role_id
    role = db.get(AccessRole, role_id) if role_id else None
    if role is None:
        return False
    return role.is_admin or db.get(AccessRolePermission, (role.id, app_key, permission)) is not None


def chain_for(db: Session, app: str, kind: str, requester: Identity | None, extra: list[dict] | None = None) -> list[dict]:
    """The slip's steps, in order: [{label, approver (Identity) | app_key + permission}]."""
    steps: list[dict] = []
    if requester is not None:
        for manager in managers_chain(db, requester)[:MAX_MANAGERS]:
            steps.append({"label": role_name(db, manager) or ("Manager" if not steps else "Next manager"), "approver": manager})
    if not steps:
        label, app_key, permission = FALLBACK.get((app, kind), ("Approver", app, f"{kind}.approve"))
        steps.append({"label": label, "app_key": app_key, "permission": permission})
    for group in extra or []:
        if isinstance(group, dict) and group.get("app") and group.get("permission"):
            steps.append({"label": _text(group.get("label"), 80) or "Approver", "app_key": _text(group["app"], 40), "permission": _text(group["permission"], 64)})
    return steps


# ---- opening and closing --------------------------------------------------------------------


def next_number(db: Session, company_id: str) -> str:
    n = db.scalar(select(func.count()).select_from(Approval).where(Approval.company_id == company_id)) or 0
    while True:
        n += 1
        number = f"AR-{n:06d}"
        if db.scalar(select(Approval.id).where(Approval.company_id == company_id, Approval.number == number)) is None:
            return number


def pending_for(db: Session, company_id: str, app: str, kind: str, record_id: str) -> Approval | None:
    return db.scalar(select(Approval).where(Approval.company_id == company_id, Approval.app == app, Approval.kind == kind,
                                            Approval.record_id == record_id, Approval.status == "pending").limit(1))


def latest_for(db: Session, company_id: str, app: str, kind: str, record_id: str) -> Approval | None:
    return db.scalar(select(Approval).where(Approval.company_id == company_id, Approval.app == app, Approval.kind == kind,
                                            Approval.record_id == record_id).order_by(Approval.created_at.desc(), Approval.no.desc()).limit(1))


def open_slip(db: Session, company: Company, app: str, data: dict) -> Approval | None:
    """A slip for an app's record (the event approval.requested). One pending slip per record: asked again while one
    waits, the waiting one stands. A record whose last slip was returned gets a new one, linked to it."""
    from modules.platform.audit import audit

    kind, record_id = _text(data.get("kind"), 40), _text(data.get("id"), 36)
    if not kind or not record_id:
        return None
    waiting = pending_for(db, company.id, app, kind, record_id)
    if waiting is not None:
        return waiting
    before = latest_for(db, company.id, app, kind, record_id)
    asked = data.get("requester") if isinstance(data.get("requester"), dict) else {}
    requester = person_of(db, company.id, asked.get("identityId"), asked.get("email"))
    slip = Approval(company_id=company.id, number=next_number(db, company.id), app=app, kind=kind, record_id=record_id,
                    record_number=_text(data.get("number"), 60), record_url=_text(data.get("url"), 300),
                    title=_text(data.get("title"), 200) or f"{kind.replace('_', ' ').capitalize()} {data.get('number') or ''}".strip(),
                    summary=data.get("summary") if isinstance(data.get("summary"), dict) else None,
                    requested_by_id=requester.id if requester else None,
                    requested_by_name=(requester.full_name if requester else _text(asked.get("name"), 120)) or "Someone",
                    requested_by_email=(requester.email if requester else _text(asked.get("email"), 254)),
                    status="pending", replaces_id=before.id if before is not None and before.status != "approved" else None)
    db.add(slip)
    db.flush()
    for i, step in enumerate(chain_for(db, app, kind, requester, data.get("groupSteps") if isinstance(data.get("groupSteps"), list) else None)):
        approver = step.get("approver")
        db.add(ApprovalStep(approval_id=slip.id, position=i, label=step["label"][:80], status="waiting",
                            approver_id=approver.id if approver else None, approver_name=approver.full_name if approver else None,
                            app_key=step.get("app_key"), permission=step.get("permission")))
    for item in (data.get("attachments") or [])[:MAX_FILES]:
        if isinstance(item, dict) and _text(item.get("label"), 120):
            db.add(ApprovalAttachment(approval_id=slip.id, kind="record", label=_text(item["label"], 120), app=_text(item.get("app"), 40),
                                      record_kind=_text(item.get("kind"), 40), record_id=_text(item.get("id"), 36),
                                      record_number=_text(item.get("number"), 60), url=_text(item.get("url"), 300), added_by=slip.requested_by_name))
    db.flush()
    audit(db, slip.requested_by_email or slip.requested_by_name, "approval.opened", category="admin", target=slip.number,
          target_type="approval", target_id=slip.id, company_id=company.id, fields=[kind])
    return slip


def withdraw(db: Session, company: Company, app: str, data: dict) -> Approval | None:
    """The app decided the record another way (an administrator approved it there, it was cancelled): the waiting slip
    is cancelled with the reason, and no decision is sent back."""
    from modules.platform.audit import audit

    kind, record_id = _text(data.get("kind"), 40), _text(data.get("id"), 36)
    slip = pending_for(db, company.id, app, kind or "", record_id or "") if kind and record_id else None
    if slip is None:
        return None
    for step in steps_of(db, slip):
        if step.status == "waiting":
            step.status = "skipped"
    slip.status, slip.finished_at, slip.note = "cancelled", now(), _text(data.get("reason"), 500)
    audit(db, _text(data.get("by"), 254) or app, "approval.cancelled", category="admin", target=slip.number, target_type="approval",
          target_id=slip.id, company_id=company.id)
    return slip


# ---- acting ---------------------------------------------------------------------------------


def steps_of(db: Session, slip: Approval) -> list[ApprovalStep]:
    return list(db.scalars(select(ApprovalStep).where(ApprovalStep.approval_id == slip.id).order_by(ApprovalStep.position)))


def current(db: Session, slip: Approval) -> ApprovalStep | None:
    if slip.status != "pending":
        return None
    return next((s for s in steps_of(db, slip) if s.status == "waiting"), None)


def is_requester(slip: Approval, person: Identity) -> bool:
    return slip.requested_by_id == person.id or bool(slip.requested_by_email and slip.requested_by_email.lower() == person.email.lower())


def acts_as(db: Session, slip: Approval, step: ApprovalStep | None, person: Identity) -> str | None:
    """How this person may act on the step that waits: approver, holder, administrator, or None. Never on their own."""
    if step is None or slip.company_id != person.company_id or is_requester(slip, person) or person.status != "active":
        return None
    if step.approver_id and step.approver_id == person.id:
        return "approver"
    if step.app_key and step.permission and holds(db, person, step.app_key, step.permission):
        return "holder"
    if runs_company(db, person):
        return "administrator"
    return None


def may_see(db: Session, slip: Approval, person: Identity) -> bool:
    if slip.company_id != person.company_id:
        return False
    if is_requester(slip, person) or runs_company(db, person):
        return True
    for step in steps_of(db, slip):
        if step.approver_id == person.id or step.acted_by_id == person.id:
            return True
        if step.app_key and step.permission and holds(db, person, step.app_key, step.permission):
            return True
    return False


def _decided(db: Session, slip: Approval, decision: str, person: Identity, note: str | None) -> None:
    """The app hears the slip's end (approval.decided, to that app only): it approves or rejects its record as the
    last one who acted."""
    from modules.platform import events

    company = db.get(Company, slip.company_id)
    events.publish(db, company, "approval.decided", {
        "app": slip.app, "kind": slip.kind, "id": slip.record_id, "number": slip.record_number,
        "approval": {"id": slip.id, "number": slip.number}, "decision": decision, "note": note,
        "by": {"identityId": person.id, "email": person.email, "name": person.full_name},
    })


def sign(db: Session, slip: Approval, person: Identity, note: str | None) -> ApprovalStep:
    """Signs the step that waits, with their Platform signature when they have one; the last signature approves."""
    from modules.platform import signatures
    from modules.platform.audit import audit

    step = current(db, slip)
    if step is None:
        raise Refused("This slip isn't waiting for anyone: it's already " + slip.status + ".")
    how = acts_as(db, slip, step, person)
    if how is None:
        if is_requester(slip, person):
            raise Refused("You can't approve your own request.", 403)
        raise Refused(f"This step waits for {step.approver_name or 'its approvers'}, not you.", 403)
    account = account_of(db, person)
    signature = signatures.current(db, account.id) if account else None
    step.status, step.note, step.acted_by_id, step.acted_by_name, step.acted_as, step.acted_at = "signed", _text(note, 500), person.id, person.full_name, how, now()
    step.signature_id = signature.id if signature else None
    audit(db, person.email, "approval.signed", category="admin", target=slip.number, target_type="approval", target_id=slip.id,
          company_id=slip.company_id, fields=[step.label] + (["as administrator"] if how == "administrator" else []))
    if current(db, slip) is None:
        slip.status, slip.finished_at = "approved", now()
        _decided(db, slip, "approved", person, _text(note, 500))
    return step


def give_back(db: Session, slip: Approval, person: Identity, note: str) -> ApprovalStep:
    """Returns the slip with a note: it ends here; the requester changes the record and sends it again."""
    from modules.platform.audit import audit

    note = (note or "").strip()
    if len(note) < 3:
        raise Refused("Say why it goes back, so they know what to change.", 422)
    step = current(db, slip)
    if step is None:
        raise Refused("This slip isn't waiting for anyone: it's already " + slip.status + ".")
    how = acts_as(db, slip, step, person)
    if how is None:
        raise Refused("You can't return your own request: cancel it instead." if is_requester(slip, person)
                      else f"This step waits for {step.approver_name or 'its approvers'}, not you.", 403)
    step.status, step.note, step.acted_by_id, step.acted_by_name, step.acted_as, step.acted_at = "returned", note[:500], person.id, person.full_name, how, now()
    for later in steps_of(db, slip):
        if later.status == "waiting":
            later.status = "skipped"
    slip.status, slip.finished_at, slip.note = "returned", now(), note[:500]
    audit(db, person.email, "approval.returned", category="admin", target=slip.number, target_type="approval", target_id=slip.id,
          company_id=slip.company_id, fields=[step.label])
    _decided(db, slip, "returned", person, note[:500])
    return step


def file_type(data: bytes) -> str | None:
    return next((kind for start, kind in FILE_TYPES.items() if data.startswith(start)), None)


def add_file(db: Session, slip: Approval, person: Identity, label: str, file_name: str, data: bytes) -> ApprovalAttachment:
    """A photo or document added to a waiting slip, by anyone who may see it."""
    from modules.platform.audit import audit

    if slip.status != "pending":
        raise Refused("Files are added while the slip waits.")
    kind = file_type(data)
    if kind is None:
        raise Refused("Add a PDF, PNG or JPEG.", 422)
    if len(data) > MAX_FILE_BYTES:
        raise Refused("Files up to 5 MB.", 422)
    if (db.scalar(select(func.count()).select_from(ApprovalAttachment).where(ApprovalAttachment.approval_id == slip.id)) or 0) >= MAX_FILES:
        raise Refused(f"A slip holds up to {MAX_FILES} attachments.")
    item = ApprovalAttachment(approval_id=slip.id, kind="file", label=(label or "").strip()[:120] or file_name[:120], file_name=file_name[:200] or "file",
                              content_type=kind, data=data, size=len(data), added_by=person.full_name)
    db.add(item)
    db.flush()
    audit(db, person.email, "approval.file_added", category="admin", target=slip.number, target_type="approval", target_id=slip.id,
          company_id=slip.company_id, fields=[item.label])
    return item
