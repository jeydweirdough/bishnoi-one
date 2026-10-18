"""Promotional materials: designed by the marketing assistant, approved by the
pharmacist in Pharmacy, produced by the executive office, and given out to the
CRM's teams once their manager approves. Each design version keeps its file
(in nbad_stored_files, the database itself) and the pharmacist's comments.

The Marketing Assistant role is added with the materials area; the Executive
Assistant may produce them; the Compliance Officer and the Auditor see them.
A role an administrator has changed keeps its changes; only what's new is
added. (Administrator holds everything already.)

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

FIRST = 40000001
NUMBERED = ("nbad_promo_materials", "nbad_promo_distributions")
ROLE_EXEC_ASST_ID = "00000000-0000-4000-8000-000000000002"
ROLE_COMPLIANCE_ID = "00000000-0000-4000-8000-000000000003"
ROLE_AUDITOR_ID = "00000000-0000-4000-8000-000000000004"
ROLE_MARKETING_ID = "00000000-0000-4000-8000-000000000005"
GRANTS = {
    ROLE_EXEC_ASST_ID: ("materials.view", "materials.produce"),
    ROLE_COMPLIANCE_ID: ("materials.view",),
    ROLE_AUDITOR_ID: ("materials.view",),
    ROLE_MARKETING_ID: ("materials.view", "materials.create", "materials.edit", "materials.distribute"),
}


def upgrade() -> None:
    bind = op.get_bind()
    have = set(sa.inspect(bind).get_table_names())
    if "nbad_stored_files" not in have:
        op.create_table(
            "nbad_stored_files",
            sa.Column("ref", sa.String(32), primary_key=True),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "nbad_promo_materials" not in have:
        op.create_table(
            "nbad_promo_materials",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("no", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(160), nullable=False, index=True),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("product", sa.String(160), nullable=True),
            sa.Column("description", sa.String(1000), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by_name", sa.String(140), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('draft', 'pharmacy_review', 'returned', 'rejected', 'approved', 'in_production', 'available', 'retired')", name="nbad_promo_status"),
        )
    if "nbad_promo_versions" not in have:
        op.create_table(
            "nbad_promo_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("material_id", sa.String(36), sa.ForeignKey("nbad_promo_materials.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("file_ref", sa.String(32), nullable=True),
            sa.Column("file_name", sa.String(200), nullable=True),
            sa.Column("notes", sa.String(1000), nullable=True),
            sa.Column("review", sa.String(10), nullable=False, server_default="draft"),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_by_name", sa.String(140), nullable=True),
            sa.Column("pharmacy_number", sa.String(40), nullable=True),
            sa.Column("comments", sa.String(2000), nullable=True),
            sa.Column("reviewed_by", sa.String(140), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sync_error", sa.String(300), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("review IN ('draft', 'waiting', 'approved', 'returned', 'rejected')", name="nbad_promo_version_review"),
        )
    if "nbad_promo_productions" not in have:
        op.create_table(
            "nbad_promo_productions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("material_id", sa.String(36), sa.ForeignKey("nbad_promo_materials.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("supplier", sa.String(160), nullable=True),
            sa.Column("cost", sa.Float(), nullable=True),
            sa.Column("ordered_on", sa.Date(), nullable=True),
            sa.Column("expected_on", sa.Date(), nullable=True),
            sa.Column("received_on", sa.Date(), nullable=True),
            sa.Column("status", sa.String(10), nullable=False, server_default="ordered"),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("by_name", sa.String(140), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('ordered', 'received', 'cancelled')", name="nbad_promo_production_status"),
        )
    if "nbad_promo_distributions" not in have:
        op.create_table(
            "nbad_promo_distributions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("no", sa.Integer(), nullable=True),
            sa.Column("material_id", sa.String(36), sa.ForeignKey("nbad_promo_materials.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("team_id", sa.String(36), nullable=False),
            sa.Column("team_name", sa.String(140), nullable=False),
            sa.Column("recipient_id", sa.String(36), nullable=True),
            sa.Column("recipient_name", sa.String(140), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("purpose", sa.String(500), nullable=True),
            sa.Column("status", sa.String(12), nullable=False, server_default="for_approval"),
            sa.Column("requested_by_name", sa.String(140), nullable=True),
            sa.Column("manager_name", sa.String(140), nullable=True),
            sa.Column("decision_note", sa.String(500), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("distributed_on", sa.Date(), nullable=True),
            sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sync_error", sa.String(300), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('for_approval', 'approved', 'rejected', 'distributed', 'cancelled')", name="nbad_promo_distribution_status"),
        )

    # Record numbers, as the record_numbers migration gives the others.
    postgres = bind.dialect.name == "postgresql"
    for table in NUMBERED:
        if postgres:
            seq = f"{table}_no_seq"
            bind.execute(sa.text(f"create sequence if not exists {seq} start with {FIRST}"))
            bind.execute(sa.text(f"alter table {table} alter column no set default nextval('{seq}')"))
            bind.execute(sa.text(f"alter sequence {seq} owned by {table}.no"))
        if f"{table}_no" not in {i["name"] for i in sa.inspect(bind).get_indexes(table)}:
            op.create_index(f"{table}_no", table, ["no"], unique=True)

    # The Marketing Assistant role (a new database has it from the first migration already).
    roles = sa.table("nbad_roles", sa.column("id"), sa.column("name"), sa.column("description"), sa.column("is_system"), sa.column("created_at"))
    existing = set(bind.execute(sa.text("SELECT id FROM nbad_roles")).scalars().all())
    named = set(n.lower() for n in bind.execute(sa.text("SELECT name FROM nbad_roles")).scalars().all())
    if ROLE_MARKETING_ID not in existing and "marketing assistant" not in named:
        from datetime import UTC, datetime

        op.bulk_insert(roles, [{
            "id": ROLE_MARKETING_ID,
            "name": "Marketing Assistant",
            "description": "Designs promotional materials, sends them for the pharmacist's approval, and gives them out once the manager approves.",
            "is_system": False,
            "created_at": datetime.now(UTC),
        }])
        existing.add(ROLE_MARKETING_ID)

    grants = sa.table("nbad_role_permissions", sa.column("role_id"), sa.column("permission"))
    for role_id, permissions in GRANTS.items():
        if role_id not in existing:
            continue
        held = set(bind.execute(sa.text("SELECT permission FROM nbad_role_permissions WHERE role_id = :r"), {"r": role_id}).scalars().all())
        new = [p for p in permissions if p not in held]
        if new:
            op.bulk_insert(grants, [{"role_id": role_id, "permission": p} for p in new])


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM nbad_role_permissions WHERE permission LIKE 'materials.%'"))
    for table in ("nbad_promo_distributions", "nbad_promo_productions", "nbad_promo_versions", "nbad_promo_materials", "nbad_stored_files"):
        op.drop_table(table)
        if bind.dialect.name == "postgresql":
            bind.execute(sa.text(f"drop sequence if exists {table}_no_seq"))
