"""Guarantee letters are kept in the database (stored_files), not on disk, so
a server without a lasting disk (Vercel) keeps them. Letters already on disk
(FILES_DIR, .data/files by default) are copied in; ones missing there are
left out, and their quotes say they have no letter on file, as before.

Revision ID: 0012
Revises: 0011
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op

from app.config import get_settings

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    files = op.create_table(
        "stored_files",
        sa.Column("ref", sa.String(32), primary_key=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    folder = Path(get_settings().files_dir)
    if not folder.is_dir():
        return
    rows = []
    now = datetime.now(UTC)
    for (letter,) in op.get_bind().execute(sa.text("SELECT letter FROM quotes WHERE letter IS NOT NULL")):
        letter = json.loads(letter) if isinstance(letter, str) else letter
        f = (letter or {}).get("file")
        path = folder / f"{f['ref']}{f['ext']}" if f else None
        if path is not None and path.is_file():
            rows.append({"ref": f["ref"], "content_type": f["contentType"], "data": path.read_bytes(), "created_at": now})
    if rows:
        op.bulk_insert(files, rows)


def downgrade() -> None:
    op.drop_table("stored_files")
