"""Customer codes: CUS-000001 on, given by the system and never changed.
Customers already here get theirs in the order they were added.

Revision ID: 0037
Revises: 0036
"""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "code" not in {c["name"] for c in sa.inspect(bind).get_columns("nbcm_companies")}:
        with op.batch_alter_table("nbcm_companies") as batch:
            batch.add_column(sa.Column("code", sa.String(20), nullable=True))
            batch.create_index("ix_nbcm_companies_code", ["code"], unique=True)
    companies = sa.table("nbcm_companies", sa.column("id"), sa.column("code"), sa.column("created_at"))
    last = bind.scalar(sa.select(sa.func.max(companies.c.code)).where(companies.c.code.like("CUS-%")))
    number = int(last.rsplit("-", 1)[1]) if last else 0
    for (company_id,) in bind.execute(sa.select(companies.c.id).where(companies.c.code.is_(None)).order_by(companies.c.created_at, companies.c.id)).all():
        number += 1
        bind.execute(companies.update().where(companies.c.id == company_id).values(code=f"CUS-{number:06d}"))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_companies") as batch:
        batch.drop_index("ix_nbcm_companies_code")
        batch.drop_column("code")
