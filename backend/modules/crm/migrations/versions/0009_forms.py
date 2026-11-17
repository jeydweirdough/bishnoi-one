"""Forms: each record's form is a layout an admin shapes (Settings → Forms),
with sections and every field on it, built in or added.

The custom fields made so far are carried over into a "More details" section,
and the pick-lists become the options of the fields they served (Industry,
Form, Unit). The old tables go.

Revision ID: 0009
Revises: 0008
"""

import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# Every form as it starts: sections, then (key, label, type, locked). Written out
# here so later changes to the app never rewrite what this did.
LAYOUTS = {
    "company": [
        ("The company", 2, [("name", "Name", "text", True), ("status", "Type", "status", True), ("industry", "Industry", "choice", False), ("website", "Website", "url", False)]),
        ("How to reach them", 2, [("email", "Email", "email", False), ("phone", "Phone", "phone", False), ("address", "Address", "text", False), ("city", "City", "text", False), ("country", "Country", "text", False)]),
        ("Who looks after it", 2, [("ownerId", "Owner", "owner", True), ("notes", "Notes", "long_text", False)]),
    ],
    "contact": [
        ("The person", 2, [("firstName", "First name", "text", True), ("lastName", "Last name", "text", False), ("jobTitle", "Job title", "text", False), ("companyId", "Company", "company", False)]),
        ("How to reach them", 2, [("email", "Email", "email", False), ("phone", "Phone", "phone", False), ("mobile", "Mobile", "phone", False)]),
        ("Who looks after them", 2, [("ownerId", "Owner", "owner", True), ("notes", "Notes", "long_text", False)]),
    ],
    "product": [
        ("The product", 2, [("code", "Code", "text", True), ("name", "Name", "text", True), ("genericName", "Generic name", "text", False), ("strength", "Strength", "text", False), ("form", "Form", "choice", False), ("unit", "Sold by", "choice", True), ("isActive", "On sale", "yes_no", True)]),
    ],
    "quote": [
        ("More about this quote", 1, [("notes", "Notes", "long_text", False)]),
    ],
}
# Which pick-list feeds which field's options.
LISTS = {("company", "industry"): "industry", ("product", "form"): "product_form", ("product", "unit"): "product_unit"}


def upgrade() -> None:
    sections = op.create_table(
        "form_sections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity", sa.String(12), nullable=False, index=True),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("columns", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    fields = op.create_table(
        "form_fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity", sa.String(12), nullable=False, index=True),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("type", sa.String(12), nullable=False),
        sa.Column("standard", sa.Boolean(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column("in_list", sa.Boolean(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("help_text", sa.String(200), nullable=True),
        sa.Column("placeholder", sa.String(80), nullable=True),
        sa.Column("section_id", sa.String(36), sa.ForeignKey("form_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("entity", "key", name="uq_form_field_key"),
    )
    db = op.get_bind()
    picked: dict[str, list[str]] = {}
    for name, value in db.execute(sa.text("SELECT list, value FROM pick_list_items WHERE is_active ORDER BY sort_order, value")):
        picked.setdefault(name, []).append(value)

    section_rows, field_rows = [], []
    for entity, layout in LAYOUTS.items():
        for n, (title, columns, items) in enumerate(layout):
            sid = str(uuid.uuid4())
            section_rows.append({"id": sid, "entity": entity, "title": title, "columns": columns, "sort_order": n})
            for m, (key, label, kind, locked) in enumerate(items):
                field_rows.append(
                    {
                        "id": str(uuid.uuid4()), "entity": entity, "key": key, "label": label, "type": kind, "standard": True,
                        "locked": locked, "required": locked, "hidden": False, "in_list": False,
                        "options": picked.get(LISTS.get((entity, key), ""), []), "help_text": None, "placeholder": None,
                        "section_id": sid, "sort_order": m,
                    }
                )
        # The custom fields made so far, in a section of their own.
        old = list(db.execute(sa.text("SELECT key, label, type, options, required, in_list, is_active FROM custom_fields WHERE entity = :e ORDER BY sort_order, label"), {"e": entity}))
        if old:
            sid = str(uuid.uuid4())
            section_rows.append({"id": sid, "entity": entity, "title": "More details", "columns": 2, "sort_order": len(layout)})
            for m, (key, label, kind, options, required, in_list, active) in enumerate(old):
                field_rows.append(
                    {
                        "id": str(uuid.uuid4()), "entity": entity, "key": key, "label": label, "type": kind, "standard": False,
                        "locked": False, "required": bool(required), "hidden": not active, "in_list": bool(in_list),
                        "options": json.loads(options) if isinstance(options, str) else (options or []),
                        "help_text": None, "placeholder": None, "section_id": sid, "sort_order": m,
                    }
                )
    op.bulk_insert(sections, section_rows)
    op.bulk_insert(fields, field_rows)
    op.drop_table("custom_fields")
    op.drop_table("pick_list_items")


def downgrade() -> None:
    raise NotImplementedError("Forms can't be turned back into custom fields and pick-lists. Restore the .before-0009 copy instead.")
