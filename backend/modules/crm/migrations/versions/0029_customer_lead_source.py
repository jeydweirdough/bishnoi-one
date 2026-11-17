"""Lead source on customers: how they first came to us, from the same list as
deals (Settings → Deal stages), and on the customer form after Industry.

Revision ID: 0029
Revises: 0028
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("nbcm_companies")}
    if "lead_source" not in columns:
        with op.batch_alter_table("nbcm_companies") as batch:
            batch.add_column(sa.Column("lead_source", sa.String(60), nullable=True))
    fields = sa.table(
        "nbcm_form_fields",
        sa.column("id"), sa.column("entity"), sa.column("key"), sa.column("label"), sa.column("type"), sa.column("standard"),
        sa.column("locked"), sa.column("required"), sa.column("hidden"), sa.column("in_list"), sa.column("options", sa.JSON),
        sa.column("help_text"), sa.column("placeholder"), sa.column("section_id"), sa.column("sort_order"),
    )
    if bind.execute(sa.select(fields.c.id).where(fields.c.entity == "company", fields.c.key == "leadSource")).first():
        return
    # Next to Industry, wherever an admin has put that; else in the first section.
    industry = bind.execute(sa.select(fields.c.section_id, fields.c.sort_order).where(fields.c.entity == "company", fields.c.key == "industry")).first()
    if industry is not None and industry.section_id:
        section, after = industry.section_id, industry.sort_order
    else:
        first = bind.execute(sa.text("SELECT id FROM nbcm_form_sections WHERE entity = 'company' ORDER BY sort_order LIMIT 1")).first()
        if first is None:
            return
        section, after = first.id, -1
    bind.execute(fields.update().where(fields.c.section_id == section, fields.c.sort_order > after).values(sort_order=fields.c.sort_order + 1))
    bind.execute(
        fields.insert().values(
            id=str(uuid.uuid4()), entity="company", key="leadSource", label="Lead source", type="choice", standard=True, locked=False,
            required=False, hidden=False, in_list=False, options=[], help_text="How they first came to us.", placeholder=None,
            section_id=section, sort_order=after + 1,
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM nbcm_form_fields WHERE entity = 'company' AND key = 'leadSource'")
    with op.batch_alter_table("nbcm_companies") as batch:
        batch.drop_column("lead_source")
