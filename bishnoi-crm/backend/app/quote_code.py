"""Quotation templates written as code: HTML the company curates, with fields.

A template of kind "code" keeps its HTML in its design ("html"). Fields are
written %customer_name%, %quote_no%, %total%...; each is replaced with the
quote's own value, escaped, so a customer named "<b>" prints as typed. The
products repeat between %lines_start% and %lines_end%, with %line_qty%,
%line_price%... inside; or %items_table% puts in a ready table. %logo% and
%signature% are the template's images.

What comes out is cleaned with an allow-list (nh3): page tags, tables, images
and the company's own <style> stay; scripts, event handlers, frames, forms and
outside links go. So whatever is typed into a template, a printed quote can't
run anything or call anywhere.
"""

import base64
import html as html_lib
import re
from typing import Any

import nh3

MAX_HTML = 200_000  # characters

# The fields, as the editor lists them: (field, what it is).
FIELDS: list[tuple[str, str, str]] = [
    # group, field, what it is
    ("Your company", "company_name", "Company name"),
    ("Your company", "company_address", "Company address"),
    ("Your company", "company_phone", "Company phone"),
    ("Your company", "company_tin", "Company TIN"),
    ("Your company", "payable_to", "Checks payable to"),
    ("Your company", "logo", "The logo (an image)"),
    ("The quote", "heading", "Heading (e.g. PRICE QUOTATION)"),
    ("The quote", "quote_no", "Quote number"),
    ("The quote", "control_no", "Control number"),
    ("The quote", "date", "Date issued"),
    ("The quote", "valid_until", "Valid until"),
    ("The quote", "prepared_by", "Sales representative"),
    ("The quote", "team", "Team"),
    ("The quote", "total", "Grand total"),
    ("The quote", "items_table", "The products, as a ready table"),
    ("The quote", "notes", "Notes"),
    ("The quote", "terms", "Terms"),
    ("The customer", "customer_name", "Patient or customer name"),
    ("The customer", "customer_phone", "Contact number"),
    ("The customer", "customer_address", "Address"),
    ("The customer", "hospital", "Hospital or clinic"),
    ("Who pays", "payer", "Who pays (the guarantee letter's issuer)"),
    ("Who pays", "letter_no", "Guarantee letter number"),
    ("Who pays", "letter_amount", "Guarantee letter amount"),
    ("Wording", "certification", "Certification"),
    ("Wording", "acceptance", "Acceptance of the guarantee letter"),
    ("Signing", "signatory_name", "Authorized representative"),
    ("Signing", "signatory_title", "Their title"),
    ("Signing", "signatory_contact", "Their contact"),
    ("Signing", "signature", "The e-signature (an image)"),
    ("Each product (between %lines_start% and %lines_end%)", "line_no", "Line number"),
    ("Each product (between %lines_start% and %lines_end%)", "line_generic", "Generic name"),
    ("Each product (between %lines_start% and %lines_end%)", "line_brand", "Brand name"),
    ("Each product (between %lines_start% and %lines_end%)", "line_product", "Product name"),
    ("Each product (between %lines_start% and %lines_end%)", "line_strength", "Strength"),
    ("Each product (between %lines_start% and %lines_end%)", "line_form", "Preparation"),
    ("Each product (between %lines_start% and %lines_end%)", "line_unit", "Unit"),
    ("Each product (between %lines_start% and %lines_end%)", "line_qty", "Quantity"),
    ("Each product (between %lines_start% and %lines_end%)", "line_price", "Unit price"),
    ("Each product (between %lines_start% and %lines_end%)", "line_discount", "Discount per unit"),
    ("Each product (between %lines_start% and %lines_end%)", "line_net", "Price after discount"),
    ("Each product (between %lines_start% and %lines_end%)", "line_total", "Line total"),
]
FIELD = re.compile(r"%([a-z][a-z0-9_.]*)%")
LINES = re.compile(r"%lines_start%(.*?)%lines_end%", re.S)

TAGS = {
    "html", "head", "body", "style", "div", "span", "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "em", "i", "u", "small", "sup", "sub",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "colgroup", "col", "caption", "ul", "ol", "li", "img", "section", "header", "footer", "main", "article", "figure", "figcaption", "blockquote", "pre", "code",
}
ATTRIBUTES = {"*": {"class", "style", "id", "align", "valign", "width", "height", "colspan", "rowspan", "title", "dir", "lang"}, "img": {"src", "alt"}}


def peso(amount: Any) -> str:
    try:
        return f"₱{float(amount):,.2f}"
    except (TypeError, ValueError):
        return ""


def _images(logo: bytes | None, logo_type: str | None, sign: bytes | None, sign_type: str | None) -> dict[str, str]:
    def tag(data: bytes | None, kind: str | None, alt: str, cls: str) -> str:
        if not data or not kind:
            return ""
        return f'<img class="{cls}" alt="{alt}" src="data:{kind};base64,{base64.b64encode(data).decode()}">'

    return {"logo": tag(logo, logo_type, "Logo", "logo"), "signature": tag(sign, sign_type, "Signature", "signature")}


def values_of(doc: dict) -> dict[str, str]:
    """The quote's values, by field name, as text (escaped later)."""
    d = doc.get("design") or {}
    return {
        "company_name": d.get("companyName", ""), "company_address": d.get("address", ""), "company_phone": d.get("phone", ""), "company_tin": d.get("tin", ""),
        "payable_to": d.get("payableTo", ""), "heading": d.get("heading", ""), "certification": d.get("certification", ""), "acceptance": d.get("acceptance", ""),
        "signatory_name": d.get("signatoryName", ""), "signatory_title": d.get("signatoryTitle", ""), "signatory_contact": d.get("signatoryContact", ""),
        "quote_no": doc.get("quoteNumber") or "", "control_no": doc.get("controlNumber") or "", "date": doc.get("date") or "", "valid_until": doc.get("validUntil") or "",
        "prepared_by": doc.get("preparedBy") or "", "team": doc.get("team") or "", "total": peso(doc.get("total")),
        "notes": doc.get("notes") or "", "terms": doc.get("terms") or "",
        "customer_name": doc.get("customer") or "", "customer_phone": doc.get("phone") or "", "customer_address": doc.get("address") or "", "hospital": doc.get("hospital") or "",
        "payer": doc.get("issuer") or "", "letter_no": doc.get("letterNumber") or "", "letter_amount": peso(doc.get("letterAmount")) if doc.get("letterAmount") else "",
    }


def line_values(line: dict) -> dict[str, str]:
    return {
        "line_no": str(line.get("no", "")), "line_generic": line.get("generic", ""), "line_brand": line.get("brand", ""), "line_product": line.get("product", ""),
        "line_strength": line.get("strength", ""), "line_form": line.get("form", ""), "line_unit": line.get("unit", ""), "line_qty": str(line.get("qty", "")),
        "line_price": peso(line.get("price")), "line_discount": peso(line.get("discount")) if line.get("discount") else "", "line_net": peso(line.get("net")), "line_total": peso(line.get("total")),
    }


def items_table(doc: dict) -> str:
    rows = "".join(
        "<tr>" + "".join(f"<td{' class=\"num\"' if k in ('line_qty', 'line_price', 'line_total') else ''}>{html_lib.escape(v)}</td>" for k, v in line_values(line).items() if k in ("line_no", "line_generic", "line_brand", "line_strength", "line_form", "line_qty", "line_price", "line_total")) + "</tr>"
        for line in doc.get("lines") or []
    )
    return (
        '<table class="items"><thead><tr><th>No.</th><th>Generic name</th><th>Brand name</th><th>Strength</th><th>Preparation</th>'
        '<th class="num">Qty</th><th class="num">Unit price</th><th class="num">Total</th></tr></thead>'
        f'<tbody>{rows}</tbody><tfoot><tr><td colspan="7" class="num"><strong>Grand total</strong></td><td class="num"><strong>{html_lib.escape(peso(doc.get("total")))}</strong></td></tr></tfoot></table>'
    )


def render(source: str, doc: dict, logo: bytes | None = None, logo_type: str | None = None, sign: bytes | None = None, sign_type: str | None = None) -> str:
    """The template, filled in with the quote, and cleaned."""
    values = values_of(doc)
    extra = doc.get("extra") or {}
    raw = {**_images(logo, logo_type, sign, sign_type), "items_table": items_table(doc)}

    def fill(text: str, more: dict[str, str] | None = None) -> str:
        def one(m: re.Match) -> str:
            name = m.group(1)
            if name in raw:
                return raw[name]
            if more and name in more:
                return html_lib.escape(more[name])
            if name in values:
                return html_lib.escape(values[name]).replace("\n", "<br>")
            if name.startswith("extra.") and name[6:] in extra:
                return html_lib.escape(str(extra[name[6:]] or ""))
            return m.group(0)  # not a field: left as typed, so a mistake shows

        return FIELD.sub(one, text)

    body = LINES.sub(lambda m: "".join(fill(m.group(1), line_values(line)) for line in doc.get("lines") or []), source[:MAX_HTML])
    return clean(fill(body))


def clean(text: str) -> str:
    return nh3.clean(text, tags=TAGS, clean_content_tags={"script"}, attributes=ATTRIBUTES, url_schemes={"data"}, strip_comments=True, link_rel=None)


# A starting point: the company's usual quotation, as code to change.
STARTER = """<style>
  body { font-family: Arial, sans-serif; font-size: 12px; color: #141414; margin: 0; }
  .page { padding: 32px 40px; }
  .head { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #141414; padding-bottom: 12px; }
  .logo { max-height: 64px; }
  .company { text-align: right; line-height: 1.5; }
  h1 { font-size: 18px; letter-spacing: 0.08em; text-align: center; margin: 20px 0 12px; }
  .meta { width: 100%; border-collapse: collapse; margin-bottom: 14px; }
  .meta td { padding: 3px 0; }
  .items { width: 100%; border-collapse: collapse; }
  .items th, .items td { border: 1px solid #b5b5b0; padding: 6px 8px; text-align: left; }
  .items th { background: #f1f7ee; }
  .num { text-align: right; }
  .sign { margin-top: 48px; width: 260px; text-align: center; }
  .signature { max-height: 56px; }
  .line { border-top: 1px solid #141414; padding-top: 4px; }
</style>
<div class="page">
  <div class="head">
    <div>%logo%</div>
    <div class="company">
      <strong>%company_name%</strong><br>%company_address%<br>%company_phone%<br>TIN %company_tin%
    </div>
  </div>
  <h1>%heading%</h1>
  <table class="meta">
    <tr><td><strong>Patient name:</strong> %customer_name%</td><td class="num"><strong>Control no.:</strong> %control_no%</td></tr>
    <tr><td><strong>Contact no.:</strong> %customer_phone%</td><td class="num"><strong>Date issued:</strong> %date%</td></tr>
    <tr><td><strong>Address:</strong> %customer_address%</td><td class="num"><strong>Valid until:</strong> %valid_until%</td></tr>
    <tr><td><strong>Hospital/clinic:</strong> %hospital%</td><td></td></tr>
  </table>
  %items_table%
  <p>%certification%</p>
  <p>%acceptance%</p>
  <p>%notes%</p>
  <div class="sign">
    %signature%
    <div class="line"><strong>%signatory_name%</strong><br>%signatory_title%<br>%signatory_contact%</div>
  </div>
</div>
"""


def sample_doc(design: dict, org_name: str) -> dict:
    """A quote to preview with when there's none yet: plain, made-up values."""
    return {
        "controlNumber": "PREVIEW", "quoteNumber": "Q-2026-00001", "date": "2026-10-14", "validUntil": "2026-11-13",
        "customer": "Maria Santos", "phone": "0917 123 4567", "address": "12 Rizal St, Makati", "hospital": "St. Luke's Medical Center",
        "issuer": "DSWD", "letterNumber": "GL-2026-001", "letterAmount": 1450.0, "team": "B2C", "preparedBy": "Linus Aurin",
        "lines": [
            {"no": 1, "generic": "Amoxicillin", "brand": "Amoxil", "product": "Amoxicillin 500 mg", "strength": "500 mg", "form": "Capsule", "unit": "box", "qty": 2, "price": 690.0, "discount": None, "net": 690.0, "total": 1380.0},
            {"no": 2, "generic": "Paracetamol", "brand": "Biogesic", "product": "Paracetamol 500 mg", "strength": "500 mg", "form": "Tablet", "unit": "box", "qty": 1, "price": 165.0, "discount": None, "net": 165.0, "total": 165.0},
        ],
        "total": 1545.0, "notes": "", "terms": "", "extra": {},
        "design": {**design, "companyName": design.get("companyName") or org_name},
    }
