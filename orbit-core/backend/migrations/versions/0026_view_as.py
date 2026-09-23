"""a Developer Admin can look through somebody's eyes

Seeing a company's screens is not the same as reading its tables. What a rep
actually sees depends on their teams, their role and their records, and the only
honest way to check it is to look at it.

So a session can be marked as driven by somebody else. It resolves as the person
-- their scopes, their screens, their figures -- and nothing can be changed
through it, and the audit log names who was really at the keyboard.

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("viewed_by_id", sa.String(36), nullable=True))
        batch.create_foreign_key("session_viewed_by", "profiles", ["viewed_by_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_constraint("session_viewed_by", type_="foreignkey")
        batch.drop_column("viewed_by_id")
