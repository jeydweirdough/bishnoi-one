"""One kind of person, and the org chart (feature plan step 4, agreed 2026-10-28).

- nbpl_accounts: one per person (email, name, the one password, the operator switch,
  status). Made from the company rows (nbpl_identities) by email, then from the staff
  (nbpl_users): Platform Admins become operators. Where passwords differ, the more
  recently changed one is kept (`python -m app.tools.accounts report` lists who).
- nbpl_identities become memberships: they keep their ids (every app knows people by
  them) and gain account_id, main_unit_id, branch_id and via_operator. Their email,
  name and password stay for one release, kept the same as the account's.
- nbpl_units: the org chart (division / department / team, a parent, a manager, the
  areas it covers). Today's departments arrive with their ids; the CRM's teams are
  brought in by `python -m app.tools.org_chart` (another database).
- nbpl_branches: where people work; today's branches arrive with their ids.
- nbpl_membership_units: a membership's units beyond its main one.

nbpl_org_units and nbpl_users are kept as they are (history). Safe to run twice.

Revision ID: 0013
Revises: 0012
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

FIRST = 40000001


def _when(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def upgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    tables = set(sa.inspect(bind).get_table_names())

    if "nbpl_accounts" not in tables:
        op.create_table(
            "nbpl_accounts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("no", sa.Integer()),
            sa.Column("email", sa.String(254), nullable=False, unique=True),
            sa.Column("full_name", sa.String(120), nullable=False),
            sa.Column("first_name", sa.String(60)),
            sa.Column("middle_initial", sa.String(4)),
            sa.Column("last_name", sa.String(60)),
            sa.Column("suffix", sa.String(10)),
            sa.Column("gender", sa.String(8)),
            sa.Column("phone", sa.String(20)),
            sa.Column("birthday", sa.Date()),
            sa.Column("password_hash", sa.String(255)),
            sa.Column("password_changed_at", sa.DateTime(timezone=True)),
            sa.Column("is_operator", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(16), nullable=False, server_default="active"),
            sa.Column("last_sign_in_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('active', 'suspended')", name="nbpl_account_status"),
        )
        op.create_index("nbpl_accounts_no", "nbpl_accounts", ["no"], unique=True)
        if postgres:
            bind.execute(sa.text(f"create sequence if not exists nbpl_accounts_no_seq start with {FIRST}"))
            bind.execute(sa.text("alter table nbpl_accounts alter column no set default nextval('nbpl_accounts_no_seq')"))
            bind.execute(sa.text("alter sequence nbpl_accounts_no_seq owned by nbpl_accounts.no"))

    if "nbpl_branches" not in tables:
        op.create_table(
            "nbpl_branches",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("address", sa.String(200)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("company_id", "name", name="nbpl_branch_name"),
        )

    if "nbpl_units" not in tables:
        op.create_table(
            "nbpl_units",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("parent_id", sa.String(36), sa.ForeignKey("nbpl_units.id", ondelete="SET NULL"), index=True),
            sa.Column("manager_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="SET NULL")),
            sa.Column("areas", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("kind IN ('division', 'department', 'team')", name="nbpl_unit_kind"),
        )

    if "nbpl_membership_units" not in tables:
        op.create_table(
            "nbpl_membership_units",
            sa.Column("membership_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("unit_id", sa.String(36), sa.ForeignKey("nbpl_units.id", ondelete="CASCADE"), primary_key=True, index=True),
        )

    columns = {c["name"] for c in sa.inspect(bind).get_columns("nbpl_identities")}
    if "account_id" not in columns:
        with op.batch_alter_table("nbpl_identities") as batch:
            batch.add_column(sa.Column("account_id", sa.String(36), sa.ForeignKey("nbpl_accounts.id", name="nbpl_identity_account", ondelete="RESTRICT")))
            batch.add_column(sa.Column("main_unit_id", sa.String(36), sa.ForeignKey("nbpl_units.id", name="nbpl_identity_unit", ondelete="SET NULL")))
            batch.add_column(sa.Column("branch_id", sa.String(36), sa.ForeignKey("nbpl_branches.id", name="nbpl_identity_branch", ondelete="SET NULL")))
            batch.add_column(sa.Column("via_operator", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_index("ix_nbpl_identities_account_id", "nbpl_identities", ["account_id"])

    bring_in(bind)


def bring_in(bind) -> None:
    """Today's people, departments and branches into the new tables (only what isn't there yet)."""
    now = datetime.now(UTC)
    accounts = {row.email: row for row in bind.execute(sa.text("select id, email, password_changed_at from nbpl_accounts"))}
    number = (bind.execute(sa.text("select max(no) from nbpl_accounts")).scalar() or FIRST - 1) + 1
    sqlite = bind.dialect.name == "sqlite"

    def make(email: str, name: str, hashed, changed, created) -> str:
        nonlocal number
        new = str(uuid.uuid4())
        values = {"id": new, "email": email, "name": name, "hash": hashed, "changed": changed, "created": created or now}
        if sqlite:
            values["no"] = number
            number += 1
            bind.execute(sa.text("insert into nbpl_accounts (id, no, email, full_name, password_hash, password_changed_at, is_operator, status, created_at) "
                                 "values (:id, :no, :email, :name, :hash, :changed, false, 'active', :created)"), values)
        else:
            bind.execute(sa.text("insert into nbpl_accounts (id, email, full_name, password_hash, password_changed_at, is_operator, status, created_at) "
                                 "values (:id, :email, :name, :hash, :changed, false, 'active', :created)"), values)
        accounts[email] = SimpleNamespace(id=new, email=email, password_changed_at=changed)
        return new

    # 1. Company rows, by email: the name and password of the most recently changed row.
    rows = bind.execute(sa.text(
        "select id, lower(trim(email)) as email, full_name, password_hash, password_changed_at, created_at, account_id from nbpl_identities"
    )).all()
    by_email: dict[str, list] = {}
    for r in rows:
        by_email.setdefault(r.email, []).append(r)
    for email, group in by_email.items():
        group.sort(key=lambda r: (_when(r.password_changed_at) is not None and r.password_hash is not None,
                                  _when(r.password_changed_at) or datetime.min.replace(tzinfo=UTC), _when(r.created_at) or now), reverse=True)
        best = group[0]
        account = accounts.get(email)
        account_id = account.id if account else make(email, best.full_name, best.password_hash, best.password_changed_at,
                                                     min((_when(r.created_at) or now) for r in group))
        for r in group:
            if r.account_id is None:
                bind.execute(sa.text("update nbpl_identities set account_id = :a where id = :id"), {"a": account_id, "id": r.id})

    # 2. Staff: joins the account with the same email (or makes one); Platform Admins are operators.
    staff = bind.execute(sa.text(
        "select lower(trim(email)) as email, full_name, first_name, middle_initial, last_name, suffix, gender, phone, birthday, "
        "password_hash, password_changed_at, created_at, role, is_active from nbpl_users"
    )).all()
    for s in staff:
        account = accounts.get(s.email)
        if account is None:
            make(s.email, s.full_name, s.password_hash, s.password_changed_at, s.created_at)
            account = accounts[s.email]
        else:
            mine = bind.execute(sa.text("select password_hash, password_changed_at from nbpl_accounts where id = :id"), {"id": account.id}).one()
            theirs, ours = _when(s.password_changed_at), _when(mine.password_changed_at)
            if mine.password_hash is None or (theirs and (ours is None or theirs > ours)):
                bind.execute(sa.text("update nbpl_accounts set password_hash = :h, password_changed_at = :c where id = :id"),
                             {"h": s.password_hash, "c": s.password_changed_at, "id": account.id})
        bind.execute(sa.text(
            "update nbpl_accounts set is_operator = :op, first_name = coalesce(first_name, :fn), middle_initial = coalesce(middle_initial, :mi), "
            "last_name = coalesce(last_name, :ln), suffix = coalesce(suffix, :sx), gender = coalesce(gender, :g), phone = coalesce(phone, :p), "
            "birthday = coalesce(birthday, :b) where id = :id"
        ), {"op": bool(s.role == "admin" and s.is_active), "fn": s.first_name, "mi": s.middle_initial, "ln": s.last_name, "sx": s.suffix,
            "g": s.gender, "p": s.phone, "b": s.birthday, "id": account.id})

    # Memberships made for a Platform Admin when they signed in (not by the company).
    made_for_admins = [r[0] for r in bind.execute(sa.text(
        "select target_id from nbpl_audit where action = 'user.created' and actor = 'Bishnoi One' and target_id is not null"
    ))]
    for membership in made_for_admins:
        bind.execute(sa.text("update nbpl_identities set via_operator = true where id = :id"), {"id": membership})

    # 3. Today's departments and branches, with their ids.
    have_units = {r[0] for r in bind.execute(sa.text("select id from nbpl_units"))}
    have_branches = {r[0] for r in bind.execute(sa.text("select id from nbpl_branches"))}
    for u in bind.execute(sa.text("select id, company_id, kind, name, location, created_at from nbpl_org_units")).all():
        if u.kind == "department" and u.id not in have_units:
            bind.execute(sa.text("insert into nbpl_units (id, company_id, kind, name, areas, is_active, created_at) "
                                 "values (:id, :c, 'department', :n, '[]', true, :at)"), {"id": u.id, "c": u.company_id, "n": u.name, "at": u.created_at or now})
        elif u.kind == "branch" and u.id not in have_branches:
            bind.execute(sa.text("insert into nbpl_branches (id, company_id, name, address, is_active, created_at) "
                                 "values (:id, :c, :n, :a, true, :at)"), {"id": u.id, "c": u.company_id, "n": u.name, "a": u.location, "at": u.created_at or now})


def downgrade() -> None:
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.drop_index("ix_nbpl_identities_account_id")
        batch.drop_column("via_operator")
        batch.drop_column("branch_id")
        batch.drop_column("main_unit_id")
        batch.drop_column("account_id")
    op.drop_table("nbpl_membership_units")
    op.drop_table("nbpl_units")
    op.drop_table("nbpl_branches")
    op.drop_index("nbpl_accounts_no", table_name="nbpl_accounts")
    op.drop_table("nbpl_accounts")
