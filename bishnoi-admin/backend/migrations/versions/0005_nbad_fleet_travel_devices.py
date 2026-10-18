"""Fleet, travel and devices: the executive assistant's trackers, moved in from
the JASMINE TASKS workbook. The company's vehicles and their renewals, the sales
team's fuel cards, doctors' hotel and flight sponsorships, and the laptops,
phones and SIMs handed out.

The starting roles get the new areas as they hold the others: the Executive
Assistant adds and changes them, the Compliance Officer and the Auditor see
them. A role an administrator has changed keeps its changes; only what's new
is added. (Administrator holds everything already.)

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

NEW_AREAS = ("vehicles", "travel", "devices")
ROLE_EXEC_ASST_ID = "00000000-0000-4000-8000-000000000002"
ROLE_COMPLIANCE_ID = "00000000-0000-4000-8000-000000000003"
ROLE_AUDITOR_ID = "00000000-0000-4000-8000-000000000004"
GRANTS = {
    ROLE_EXEC_ASST_ID: ("view", "create", "edit"),
    ROLE_COMPLIANCE_ID: ("view",),
    ROLE_AUDITOR_ID: ("view",),
}


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    if "nbad_vehicles" not in have:
        op.create_table(
            "nbad_vehicles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(140), nullable=False),
            sa.Column("plate", sa.String(20), nullable=True, index=True),
            sa.Column("year_model", sa.Integer(), nullable=True),
            sa.Column("color", sa.String(60), nullable=True),
            sa.Column("owner_name", sa.String(200), nullable=True),
            sa.Column("registration_due", sa.Date(), nullable=True),
            sa.Column("insurance_due", sa.Date(), nullable=True),
            sa.Column("pms_due", sa.Date(), nullable=True),
            sa.Column("fleet_card", sa.String(120), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            *_stamps(),
        )
    if "nbad_fleet_cards" not in have:
        op.create_table(
            "nbad_fleet_cards",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("requested_on", sa.Date(), nullable=True),
            sa.Column("holder_name", sa.String(140), nullable=False, index=True),
            sa.Column("company_name", sa.String(140), nullable=True),
            sa.Column("monthly_allowance", sa.Float(), nullable=True),
            sa.Column("allowance_note", sa.String(80), nullable=True),
            sa.Column("fuel_type", sa.String(60), nullable=True),
            sa.Column("plate", sa.String(20), nullable=True),
            sa.Column("conduction_sticker", sa.String(30), nullable=True),
            sa.Column("vehicle_unit", sa.String(140), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="processing"),
            sa.Column("card_state", sa.String(10), nullable=False, server_default="active"),
            sa.Column("notes", sa.String(500), nullable=True),
            *_stamps(),
            sa.CheckConstraint("status IN ('processing', 'handed_over', 'with_hr', 'returned')", name="nbad_fleet_card_status"),
            sa.CheckConstraint("card_state IN ('active', 'blocked')", name="nbad_fleet_card_state"),
        )
    if "nbad_travel_sponsorships" not in have:
        op.create_table(
            "nbad_travel_sponsorships",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("requested_on", sa.Date(), nullable=True),
            sa.Column("rep_name", sa.String(140), nullable=False, index=True),
            sa.Column("doctor_name", sa.String(140), nullable=False, index=True),
            sa.Column("doctor_birthdate", sa.Date(), nullable=True),
            sa.Column("kind", sa.String(10), nullable=False, server_default="hotel"),
            sa.Column("travel_dates", sa.String(140), nullable=True),
            sa.Column("starts_on", sa.Date(), nullable=True),
            sa.Column("hotel_or_flight", sa.String(200), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="for_approval"),
            sa.Column("approved_on", sa.Date(), nullable=True),
            sa.Column("next_step", sa.String(200), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            *_stamps(),
            sa.CheckConstraint("kind IN ('hotel', 'flight')", name="nbad_travel_kind"),
            sa.CheckConstraint("status IN ('for_approval', 'for_processing', 'approved', 'booked', 'cancelled')", name="nbad_travel_status"),
        )
    if "nbad_device_issues" not in have:
        op.create_table(
            "nbad_device_issues",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("issued_on", sa.Date(), nullable=True),
            sa.Column("issued_to", sa.String(200), nullable=False, index=True),
            sa.Column("laptop", sa.String(140), nullable=True),
            sa.Column("phone", sa.String(140), nullable=True),
            sa.Column("sim", sa.String(60), nullable=True),
            sa.Column("condition", sa.String(10), nullable=False, server_default="brand_new"),
            sa.Column("signed_by", sa.String(140), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            *_stamps(),
            sa.CheckConstraint("condition IN ('brand_new', 'repaired', 'used')", name="nbad_device_condition"),
        )

    # The starting roles get the new areas, beside what they already hold.
    bind = op.get_bind()
    roles = set(bind.execute(sa.text("SELECT id FROM nbad_roles")).scalars().all())
    grants = sa.table("nbad_role_permissions", sa.column("role_id"), sa.column("permission"))
    for role_id, actions in GRANTS.items():
        if role_id not in roles:
            continue
        held = set(bind.execute(sa.text("SELECT permission FROM nbad_role_permissions WHERE role_id = :r"), {"r": role_id}).scalars().all())
        new = [f"{area}.{action}" for area in NEW_AREAS for action in actions if f"{area}.{action}" not in held]
        if new:
            op.bulk_insert(grants, [{"role_id": role_id, "permission": p} for p in new])


def downgrade() -> None:
    bind = op.get_bind()
    for area in NEW_AREAS:
        bind.execute(sa.text("DELETE FROM nbad_role_permissions WHERE permission LIKE :p"), {"p": f"{area}.%"})
    for table in ("nbad_device_issues", "nbad_travel_sponsorships", "nbad_fleet_cards", "nbad_vehicles"):
        op.drop_table(table)
