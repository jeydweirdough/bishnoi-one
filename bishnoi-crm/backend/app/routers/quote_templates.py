"""Quotation templates (app/quote_templates.py): the admin sets them up under
Settings; anyone who can see a quote prints or downloads it with one.

- /admin/quote-templates: list, add, change, remove (admin.settings), or a
  manager's for their own departments' templates (department.manage).
- /admin/quote-templates/{id}/images/logo, /images/signature: an image, PNG or JPG (a drawn
  signature arrives as a PNG). /excel: the Excel form itself.
- /quote-templates/{id}/images/logo, /images/signature: the images, for the print page.
- /quotes/{id}/templates: the templates that fit a quote, the best first.
- /quotes/{id}/document?template=: the quote as the template shows it.
- /quotes/{id}/document.xlsx?template=: an Excel template, filled in.
"""

import secrets
from typing import Annotated, Any, Literal
from urllib.parse import quote as url_quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import DEPARTMENT, Access, require
from app.api import Api, changed, iso
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Issuer, Quote, QuoteTemplate, StoredFile, Team, new_id
from app.quote_templates import (
    DESIGN_DEFAULTS,
    LINE_PLACEHOLDERS,
    MAX_EXCEL_BYTES,
    MAX_IMAGE_BYTES,
    PLACEHOLDERS,
    describe,
    document,
    fill,
    find,
    image_kind,
    load,
    sheet_of,
    stored,
)
from app.routers.quotes import get_quote

router = APIRouter(tags=["quote templates"])

Manage = Annotated[Access, Depends(require(*DEPARTMENT))]
View = Annotated[Access, Depends(require("quotes.view"))]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def template_out(db: Session, t: QuoteTemplate) -> dict:
    issuer = db.get(Issuer, t.payer) if t.payer and t.payer != "self" else None
    team = db.get(Team, t.team_id) if t.team_id else None
    example = f"{(t.control_prefix or 'Q').strip('-')}-YYYY-MM-{t.control_next:0{t.control_digits}d}"
    excel = None
    if t.kind == "excel" and t.excel_ref:
        m = t.excel_map or {}
        excel = {"name": t.excel_name, "sheet": t.excel_sheet, "sheets": m.get("sheets", []), "found": m.get("found", []), "missing": m.get("missing", [])}
    return {
        "id": t.id,
        "name": t.name,
        "kind": t.kind,
        "payer": t.payer,
        "payerName": "The customer" if t.payer == "self" else issuer.name if issuer else None,
        "teamId": t.team_id,
        "teamName": team.name if team else None,
        "isActive": t.is_active,
        "controlPrefix": t.control_prefix,
        "controlNext": t.control_next,
        "controlDigits": t.control_digits,
        "controlExample": example,
        "design": {**DESIGN_DEFAULTS, **(t.design or {})},
        "hasLogo": bool(t.logo_ref),
        "hasSignature": bool(t.signature_ref),
        "excel": excel,
        "updatedAt": iso(t.updated_at),
    }


def get_template(db: Session, template_id: str, access: Access | None = None) -> QuoteTemplate:
    """A template; given who's setting it up, only one of theirs (another
    department's isn't there for a manager). Printing reads any."""
    t = db.get(QuoteTemplate, template_id)
    if t is None or (access is not None and not access.runs(t.team_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That template isn't here any more.")
    return t


@router.get("/admin/quote-templates")
def list_templates(access: Manage, db: DB) -> dict:
    rows = [t for t in db.scalars(select(QuoteTemplate).order_by(QuoteTemplate.name)) if access.runs(t.team_id)]
    issuers = db.scalars(select(Issuer).where(Issuer.is_active).order_by(Issuer.name)).all()
    teams = [t for t in db.scalars(select(Team).order_by(Team.name)) if access.runs(t.id)]
    return {
        "items": [template_out(db, t) for t in rows],
        "issuers": [{"code": i.code, "name": i.name} for i in issuers],
        "teams": [{"id": t.id, "name": t.name} for t in teams],
        "placeholders": [{"key": k, "label": v} for k, v in {**PLACEHOLDERS, **LINE_PLACEHOLDERS}.items()],
        "designDefaults": DESIGN_DEFAULTS,
    }


@router.get("/admin/quote-templates/{template_id}")
def read_template(access: Manage, db: DB, template_id: str) -> dict:
    t = get_template(db, template_id, access)
    if t.kind == "excel" and t.excel_ref:
        # what was found, as the form is read now (the reading improves; the form doesn't change)
        before = t.excel_map
        remap(db, t)
        if t.excel_map != before:
            db.commit()
    return template_out(db, t)


class DesignIn(Api):
    company_name: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=400)
    phone: str | None = Field(None, max_length=200)
    tin: str | None = Field(None, max_length=40)
    vat: Literal["vat", "non_vat"] | None = None
    payable_to: str | None = Field(None, max_length=200)
    heading: str | None = Field(None, max_length=80)
    customer_label: str | None = Field(None, max_length=40)
    certification: str | None = Field(None, max_length=2000)
    acceptance: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=2000)
    signatory_name: str | None = Field(None, max_length=120)
    signatory_title: str | None = Field(None, max_length=120)
    signatory_contact: str | None = Field(None, max_length=120)


class TemplateIn(Api):
    name: str | None = Field(None, min_length=2, max_length=120)
    kind: Literal["form", "excel"] | None = None
    payer: str | None = Field(None, max_length=40)
    team_id: str | None = None
    is_active: bool | None = None
    control_prefix: str | None = Field(None, pattern=r"^[A-Za-z0-9-]{1,20}$")
    control_next: int | None = Field(None, ge=1, le=99_999_999)
    control_digits: int | None = Field(None, ge=1, le=8)
    design: DesignIn | None = None
    excel_sheet: str | None = Field(None, max_length=120)


def check_team(access: Access, team_id: str | None) -> None:
    """A manager's templates are for their own departments; one for every team is an administrator's."""
    if not access.runs(team_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick one of your own teams.")


def check_refs(db: Session, body: TemplateIn) -> None:
    if body.payer and body.payer != "self" and db.get(Issuer, body.payer) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick who pays from the list.")
    if body.team_id and db.get(Team, body.team_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a team from the list.")


def apply(t: QuoteTemplate, body: TemplateIn, fields: dict) -> list[str]:
    done = []
    for key in ("name", "kind", "payer", "team_id", "is_active", "control_prefix", "control_next", "control_digits"):
        if key in fields and getattr(t, key) != fields[key]:
            if key in ("name", "kind", "is_active", "control_next", "control_digits") and fields[key] is None:
                continue
            setattr(t, key, fields[key])
            done.append(key)
    if body.design is not None:
        given = body.design.model_dump(by_alias=True, exclude_unset=True)
        t.design = {**(t.design or {}), **{k: (v or "") for k, v in given.items()}}
        done.append("design")
    return done


@router.post("/admin/quote-templates", status_code=status.HTTP_201_CREATED)
def create_template(access: Manage, me: CurrentUser, db: DB, body: TemplateIn) -> dict:
    if not body.name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give the template a name.")
    check_refs(db, body)
    check_team(access, body.team_id)
    t = QuoteTemplate(id=new_id(), name=body.name, kind=body.kind or "form", design={}, is_active=True, control_next=1, control_digits=4)
    apply(t, body, changed(body))
    db.add(t)
    audit(db, me, "quote_template.created", target=t.name, target_type="quote_template", target_id=t.id)
    db.commit()
    return template_out(db, t)


def remap(db: Session, t: QuoteTemplate) -> None:
    """Finds the form's parts again, on the sheet chosen."""
    data = stored(db, t.excel_ref)
    if data is None:
        return
    book = load(data.data)
    ws = sheet_of(book, t.excel_sheet)
    t.excel_sheet = ws.title
    t.excel_map = {"sheets": book.sheetnames, **describe(find(ws))}


@router.patch("/admin/quote-templates/{template_id}")
def update_template(access: Manage, me: CurrentUser, db: DB, template_id: str, body: TemplateIn) -> dict:
    t = get_template(db, template_id, access)
    check_refs(db, body)
    fields = changed(body)
    if "team_id" in fields:
        check_team(access, fields["team_id"])
    done = apply(t, body, fields)
    if "excel_sheet" in fields and fields["excel_sheet"] != t.excel_sheet:
        t.excel_sheet = fields["excel_sheet"]
        remap(db, t)
        done.append("excel_sheet")
    if done:
        audit(db, me, "quote_template.updated", target=t.name, target_type="quote_template", target_id=t.id, fields=done)
    db.commit()
    return template_out(db, t)


@router.delete("/admin/quote-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(access: Manage, me: CurrentUser, db: DB, template_id: str) -> Response:
    t = get_template(db, template_id, access)
    for ref in (t.logo_ref, t.signature_ref, t.excel_ref):
        if f := stored(db, ref):
            db.delete(f)
    audit(db, me, "quote_template.deleted", target=t.name, target_type="quote_template", target_id=t.id)
    db.delete(t)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def replace_file(db: Session, old: str | None, data: bytes, content_type: str) -> str:
    if f := stored(db, old):
        db.delete(f)
    ref = secrets.token_hex(16)
    db.add(StoredFile(ref=ref, content_type=content_type, data=data))
    return ref


Image = Literal["logo", "signature"]


@router.post("/admin/quote-templates/{template_id}/images/{which}")
async def upload_image(access: Manage, me: CurrentUser, db: DB, template_id: str, which: Image, file: Annotated[UploadFile, File()]) -> dict:
    t = get_template(db, template_id, access)
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The image is over 2 MB. Use a smaller one.")
    kind = image_kind(data)
    if kind is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use a PNG or JPG image.")
    ref = replace_file(db, getattr(t, f"{which}_ref"), data, kind[0])
    setattr(t, f"{which}_ref", ref)
    audit(db, me, "quote_template.updated", target=t.name, target_type="quote_template", target_id=t.id, fields=[which])
    db.commit()
    return template_out(db, t)


@router.delete("/admin/quote-templates/{template_id}/images/{which}")
def remove_image(access: Manage, me: CurrentUser, db: DB, template_id: str, which: Image) -> dict:
    t = get_template(db, template_id, access)
    if f := stored(db, getattr(t, f"{which}_ref")):
        db.delete(f)
    setattr(t, f"{which}_ref", None)
    audit(db, me, "quote_template.updated", target=t.name, target_type="quote_template", target_id=t.id, fields=[which])
    db.commit()
    return template_out(db, t)


@router.post("/admin/quote-templates/{template_id}/excel")
async def upload_excel(access: Manage, me: CurrentUser, db: DB, template_id: str, file: Annotated[UploadFile, File()]) -> dict:
    t = get_template(db, template_id, access)
    data = await file.read(MAX_EXCEL_BYTES + 1)
    if len(data) > MAX_EXCEL_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file is over 5 MB. Keep only the quotation sheet, or remove pictures.")
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use an Excel workbook (.xlsx).")
    try:
        book = load(data)
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That file couldn't be read as an Excel workbook.") from None
    ws = sheet_of(book, None)
    t.excel_ref = replace_file(db, t.excel_ref, data, XLSX)
    t.excel_name = (file.filename or "form.xlsx")[:200]
    t.excel_sheet = ws.title
    t.excel_map = {"sheets": book.sheetnames, **describe(find(ws))}
    t.kind = "excel"
    audit(db, me, "quote_template.updated", target=t.name, target_type="quote_template", target_id=t.id, fields=["excel"])
    db.commit()
    return template_out(db, t)


@router.get("/admin/quote-templates/{template_id}/excel")
def download_form(access: Manage, db: DB, template_id: str) -> Response:
    t = get_template(db, template_id, access)
    f = stored(db, t.excel_ref)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No Excel form is uploaded on this template.")
    return Response(f.data, media_type=XLSX, headers={"Content-Disposition": f"attachment; filename*=utf-8''{url_quote(t.excel_name or 'form.xlsx')}"})


# --- using them -------------------------------------------------------------------------------


@router.get("/quote-templates/{template_id}/images/{which}")
def read_image(access: View, db: DB, template_id: str, which: Image) -> Response:
    t = get_template(db, template_id)
    f = stored(db, getattr(t, f"{which}_ref"))
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"This template has no {which}.")
    return Response(f.data, media_type=f.content_type, headers={"Cache-Control": "private, max-age=300"})


def fitting(db: Session, quote: Quote) -> list[QuoteTemplate]:
    """Active templates for this quote's payer and team, the most specific first."""
    rows = db.scalars(select(QuoteTemplate).where(QuoteTemplate.is_active)).all()
    fits = [t for t in rows if t.payer in (None, quote.payer) and t.team_id in (None, quote.team_id)]
    fits = [t for t in fits if t.kind == "form" or t.excel_ref]
    return sorted(fits, key=lambda t: (t.payer is None, t.team_id is None, t.name.lower()))


@router.get("/quotes/{quote_id}/templates")
def quote_templates(access: View, db: DB, quote_id: str) -> dict:
    quote = get_quote(db, access, quote_id)
    return {"items": [{"id": t.id, "name": t.name, "kind": t.kind} for t in fitting(db, quote)]}


def chosen(db: Session, quote: Quote, template_id: str | None) -> QuoteTemplate:
    fits = fitting(db, quote)
    if template_id:
        t = next((t for t in fits if t.id == template_id), None)
        if t is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That template isn't set up for this quote.")
        return t
    if not fits:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No quotation template is set up for this quote.")
    return fits[0]


@router.get("/quotes/{quote_id}/document")
def quote_document(access: View, db: DB, settings: SettingsDep, quote_id: str, template: str | None = Query(None)) -> dict[str, Any]:
    quote = get_quote(db, access, quote_id)
    t = chosen(db, quote, template)
    return {"template": template_out(db, t), **document(db, quote, t, settings)}


@router.get("/quotes/{quote_id}/document.xlsx")
def quote_workbook(access: View, db: DB, settings: SettingsDep, quote_id: str, template: str | None = Query(None)) -> Response:
    quote = get_quote(db, access, quote_id)
    t = chosen(db, quote, template)
    form = stored(db, t.excel_ref)
    if t.kind != "excel" or form is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This template is designed here, not an Excel form: print it instead.")
    doc = document(db, quote, t, settings)
    logo, sign = stored(db, t.logo_ref), stored(db, t.signature_ref)
    try:
        data = fill(form.data, t.excel_sheet, doc, logo.data if logo else None, sign.data if sign else None)
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"The Excel form couldn't be filled in: {e}") from e
    name = f"{doc['controlNumber']} {quote.customer_name}.xlsx"
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f"attachment; filename*=utf-8''{url_quote(name)}", "Cache-Control": "no-store"})
