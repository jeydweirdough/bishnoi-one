"""the company's org chart: BID joins Sales, and Pharmacy is a department

The structure the company actually has:

    Sales    B2C, STC, URO, B&B (MD Telesales) | B2B (NBD, CRR)
             HOS (Hospital, Telesales) | BID (Bidding)
    Finance | Human Resource | Regulatory Affairs | In-Licensing
    Pharmacy | Executive Admin

Two things were wrong. BID was its own department although it sells like the
rest -- it already quotes, already raises orders, already has pricing rules --
so it becomes the seventh sales division and gets its Bidding team. And
Pharmacy, which was only a team under Dispatch, is a department of its own.

BID's permissions are copied from B2C, because "a sales division like the
others" is what it now is and every starting role already says what it may do
there. Admins change any of it in Settings -> Roles and Settings -> Teams; this
only moves the starting point.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

MODEL = "b2c"  # the sales division BID is made to match
# Pharmacy is made to match, since a plain department with no screens of its own
# is granted the same way. Without this it would exist and be in nobody's
# sidebar: seeding only writes roles into an empty database, so a company that
# already has roles never hears about a module added later.
DEPARTMENT_MODEL = "regulatory"

# The org chart's own order, which is the order every screen lists them in. Kept
# in step with MODULES in app/modules.py; a division a company added itself
# sorts after these, where it already is.
ORDER = (
    "b2c", "stc", "uro", "bnb", "b2b", "hos", "bid",
    "finance", "hr", "regulatory", "inlicensing", "pharmacy", "exec",
    "dispatch", "inventory",
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1. BID is a sales division. Its records, quotes and orders are untouched:
    #    only what kind of division it is changes.
    bind.execute(sa.text("UPDATE divisions SET kind = 'sales' WHERE code = 'bid'"))

    subdivisions = sa.table(
        "subdivisions",
        sa.column("org_id", sa.String), sa.column("division_code", sa.String),
        sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer), sa.column("is_active", sa.Boolean),
    )
    divisions = sa.table(
        "divisions",
        sa.column("org_id", sa.String), sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("kind", sa.String), sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean), sa.column("icon", sa.String),
    )
    permissions = sa.table(
        "role_permissions",
        sa.column("org_id", sa.String), sa.column("role_key", sa.String),
        sa.column("module_key", sa.String), sa.column("action", sa.String),
    )

    new_teams, new_divisions, new_permissions = [], [], []
    for org_id, in bind.execute(sa.text("SELECT id FROM organizations")):
        has = lambda table, **w: bind.execute(  # noqa: E731 - a local shorthand, used three times
            sa.text(f"SELECT 1 FROM {table} WHERE org_id = :org AND " + " AND ".join(f"{k} = :{k}" for k in w)),
            {"org": org_id, **w},
        ).first()

        # 2. BID's team. On a database migrated from nothing the divisions are
        #    seeded afterwards, so there is no BID yet and nothing to give it.
        if has("divisions", code="bid") and not has("subdivisions", division_code="bid", code="bidding"):
            new_teams.append({
                "org_id": org_id, "division_code": "bid", "code": "bidding",
                "name": "Bidding", "sort_order": 0, "is_active": True,
            })

        # 3. Pharmacy, a department of its own rather than a team under Dispatch.
        if not has("divisions", code="pharmacy"):
            after = bind.execute(
                sa.text("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM divisions WHERE org_id = :org"), {"org": org_id}
            ).scalar_one()
            new_divisions.append({
                "org_id": org_id, "code": "pharmacy", "name": "Pharmacy", "kind": "department",
                "sort_order": after, "is_active": True, "icon": None,
            })
            new_teams.append({
                "org_id": org_id, "division_code": "pharmacy", "code": "general",
                "name": "General", "sort_order": 0, "is_active": True,
            })
            for role_key, action in bind.execute(
                sa.text("SELECT role_key, action FROM role_permissions WHERE org_id = :org AND module_key = :model"),
                {"org": org_id, "model": DEPARTMENT_MODEL},
            ):
                new_permissions.append(
                    {"org_id": org_id, "role_key": role_key, "module_key": "pharmacy", "action": action}
                )

        # 4. BID's permissions, made to match B2C's in every role.
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE org_id = :org AND module_key = 'bid'"), {"org": org_id}
        )
        for role_key, action in bind.execute(
            sa.text("SELECT role_key, action FROM role_permissions WHERE org_id = :org AND module_key = :model"),
            {"org": org_id, "model": MODEL},
        ):
            # BID bids rather than quoting from a price list, so there is nothing
            # for its teams to price.
            if action != "prices":
                new_permissions.append(
                    {"org_id": org_id, "role_key": role_key, "module_key": "bid", "action": action}
                )

    if new_divisions:
        op.bulk_insert(divisions, new_divisions)
    if new_teams:
        op.bulk_insert(subdivisions, new_teams)
    if new_permissions:
        op.bulk_insert(permissions, new_permissions)

    # 5. And put them in the order the org chart reads, so Pharmacy sits with
    #    the other departments rather than on the end where it was added.
    for order, code in enumerate(ORDER):
        bind.execute(
            sa.text("UPDATE divisions SET sort_order = :order WHERE code = :code"), {"order": order, "code": code}
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE divisions SET kind = 'department' WHERE code = 'bid'"))
    bind.execute(sa.text("DELETE FROM subdivisions WHERE division_code = 'pharmacy'"))
    bind.execute(sa.text("DELETE FROM role_permissions WHERE module_key = 'pharmacy'"))
    bind.execute(sa.text("DELETE FROM divisions WHERE code = 'pharmacy'"))
    # The Bidding team stays: records may already be filed under it.
