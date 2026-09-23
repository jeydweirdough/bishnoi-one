"""Settings -> Data: everything this company has, going out and coming in.

Out is one dated file holding the lot, the same one app/tools/backup.py writes
nightly. In is a spreadsheet somebody already keeps, read as it is rather than
as Orbit would like it (app/sheets.py), checked row by row before a single row
is written (app/imports.py).

The owner's, not an admin's: an export carries every customer and every
person's details out of the building, and an import writes over the catalogue.
"""

import json
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.audit import audit
from app.deps import DB, CurrentOrg, CurrentUser, SettingsDep, require_owner
from app.errors import invalid
from app.imports import import_products, mapping_out
from app.sheets import Sheet, SheetError, read_sheet
from app.tools.export import ExportError, export, open_world

router = APIRouter(prefix="/admin/data", tags=["settings"], dependencies=[Depends(require_owner)])

MAX_SHEET_BYTES = 12 * 1024 * 1024


def read_upload(file: UploadFile) -> bytes:
    data = file.file.read(MAX_SHEET_BYTES + 1)
    if len(data) > MAX_SHEET_BYTES:
        raise invalid("That file is over 12MB. Split it, or send the columns you actually need.")
    if not data:
        raise invalid("That file is empty.")
    return data


def sheet_from(file: UploadFile) -> Sheet:
    try:
        return read_sheet(file.filename or "", read_upload(file))
    except SheetError as exc:
        raise invalid(str(exc)) from exc


def parse_mapping(raw: str) -> dict[str, str]:
    """The mapping arrives beside the file, so it comes as form text rather than
    a JSON body."""
    try:
        mapping = json.loads(raw)
    except ValueError as exc:
        raise invalid("The column mapping wasn't readable. Reload the page and try again.") from exc
    if not isinstance(mapping, dict) or not all(isinstance(v, str) for v in mapping.values() if v is not None):
        raise invalid("The column mapping wasn't readable. Reload the page and try again.")
    return {k: v for k, v in mapping.items() if v}


@router.get("/export")
def export_everything(
    org: CurrentOrg, settings: SettingsDep, db: DB, me: CurrentUser, cleanup: BackgroundTasks
) -> FileResponse:
    """The whole company in one file: its tables, its records and its uploads.
    The same shape `app.tools.export restore` reads, so this is a backup a
    person can take themselves, not just something to look at."""
    folder = Path(tempfile.mkdtemp(prefix="orbit-export-"))
    out = folder / f"orbit-{org.slug}-{date.today():%Y%m%d}.zip"
    try:
        export(open_world(settings), out, org=org.id, all_companies=False, force=True)
    except ExportError as exc:
        raise invalid(str(exc)) from exc
    audit(db, me, "data.exported", org.slug)
    # The file only exists to be sent; it goes once the response has gone.
    cleanup.add_task(lambda: [out.unlink(missing_ok=True), folder.rmdir()])
    return FileResponse(out, media_type="application/zip", filename=out.name)


@router.post("/products/columns")
def product_columns(db: DB, file: Annotated[UploadFile, File()]) -> dict:
    """What Orbit found in the file, and its guess at which column is which.
    Nothing is written, and nothing is remembered: the file is read and dropped."""
    return mapping_out(db, sheet_from(file), "products")


@router.post("/products/check")
def check_products(db: DB, file: Annotated[UploadFile, File()], mapping: Annotated[str, Form()]) -> dict:
    """The dry run: what would happen to every row, and nothing written."""
    return import_products(db, sheet_from(file), parse_mapping(mapping), apply=False).out()


@router.post("/products/import", status_code=status.HTTP_200_OK)
def apply_products(
    db: DB, me: CurrentUser, file: Annotated[UploadFile, File()], mapping: Annotated[str, Form()]
) -> dict:
    """Writes what the dry run described. Judged again on the way in: the
    catalogue may have moved since the person looked at the review."""
    result = import_products(db, sheet_from(file), parse_mapping(mapping), apply=True)
    db.commit()
    audit(db, me, "products.imported", f"{result.counts['new']} new, {result.counts['changed']} changed")
    return result.out()
