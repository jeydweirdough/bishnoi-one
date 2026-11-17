"""Features the owner dropped (2026-11-17), removed with their data:

- the lead inbox (Facebook, Messenger, WhatsApp, Viber, Tawk.to, web forms):
  nbcm_inbox_leads, and the permission customers.inbox;
- email from the CRM through each person's own mailbox: nbcm_mail_accounts
  (the connected mailboxes) and nbcm_email_templates (the approved emails);
- who opened which media: nbcm_media_views. The media themselves stay.

The AI lead finder kept nothing of its own. Emails already logged stay as
activities, with their screenshots (nbcm_activities.proof_ref is kept).
Recycle-bin entries of the dropped kinds go too, and binned media lose the
view rows they carried, so restoring them still works.

Plain drop_table only: nothing kept refers to these tables, so no table is
rebuilt (a SQLite batch rebuild would lose rows pointing at it).

Revision ID: 0083
Revises: 0082
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None

DROPPED = ("nbcm_inbox_leads", "nbcm_mail_accounts", "nbcm_email_templates", "nbcm_media_views")


def upgrade() -> None:
    bind = op.get_bind()
    have = set(sa.inspect(bind).get_table_names())
    for table in DROPPED:
        if table in have:
            op.drop_table(table)
    if "nbcm_role_permissions" in have:
        bind.execute(sa.text("DELETE FROM nbcm_role_permissions WHERE permission = 'customers.inbox'"))
    if "nbcm_recycle_bin" in have:
        bind.execute(sa.text("DELETE FROM nbcm_recycle_bin WHERE kind IN ('leads', 'email-templates')"))
        for entry_id, rows in bind.execute(sa.text("SELECT id, rows FROM nbcm_recycle_bin WHERE kind = 'media'")).all():
            items = json.loads(rows) if isinstance(rows, str) else rows
            kept = [i for i in items or [] if i.get("t") not in DROPPED]
            if kept != items:
                update = sa.text("UPDATE nbcm_recycle_bin SET rows = :rows WHERE id = :id").bindparams(sa.bindparam("rows", type_=sa.JSON))
                bind.execute(update, {"rows": kept, "id": entry_id})


def downgrade() -> None:
    raise NotImplementedError("0083 removed dropped features and their data (2026-11-17); restore from the copy made before it.")
