"""Customer codes start CRM- instead of CUS- (CRM-000001): the same numbers,
a new prefix. Nothing else refers to a code, so only the code changes.

Revision ID: 0038
Revises: 0037
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

companies = sa.table("nbcm_companies", sa.column("id"), sa.column("code"))


def _swap(old: str, new: str) -> None:
    bind = op.get_bind()
    for company_id, code in bind.execute(sa.select(companies.c.id, companies.c.code).where(companies.c.code.like(f"{old}-%"))).all():
        bind.execute(companies.update().where(companies.c.id == company_id).values(code=new + code[len(old):]))


def upgrade() -> None:
    _swap("CUS", "CRM")


def downgrade() -> None:
    _swap("CRM", "CUS")
