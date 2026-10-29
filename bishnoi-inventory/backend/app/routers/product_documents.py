"""Documents with products (feature plan step 15e, 2026-10-29): files kept with an item (certificate of analysis,
leaflet, CPR certificate) and whether each goes with every sale. A delivery and a sales order list the documents
of their items to send with them; the delivery note names them as enclosed.

    GET    /inventory/products/{id}/documents
    POST   /inventory/products/{id}/documents            multipart: file, name, sendWithSales
    GET    /inventory/products/{id}/documents/{doc}      the file
    PATCH  /inventory/products/{id}/documents/{doc}      {name, sendWithSales}
    DELETE /inventory/products/{id}/documents/{doc}
    GET    /inventory/orders/{id}/documents              what goes with this delivery
    GET    /inventory/sales-orders/{id}/documents        what goes with this sales order
"""

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import Field
from sqlalchemy import select

from app.access import allowed
from app.api import Api, changed, conflict, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Order, Product, ProductDocument, SalesOrder
from app.out import product_ref

router = APIRouter(prefix="/inventory", tags=["product documents"])

TYPES = {"application/pdf", "image/png", "image/jpeg",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
MAX_BYTES = 5_000_000
PER_PRODUCT = 20


def document_out(d: ProductDocument) -> dict:
    return {"id": d.id, "productId": d.product_id, "name": d.name, "fileName": d.file_name, "contentType": d.content_type, "size": d.size,
            "sendWithSales": d.send_with_sales, "createdAt": iso(d.created_at), "href": f"/inventory/products/{d.product_id}/documents/{d.id}"}


def of_product(db: DB, product_id: str) -> list[dict]:
    return [document_out(d) for d in db.scalars(select(ProductDocument).where(ProductDocument.product_id == product_id).order_by(ProductDocument.name))]


def with_sale(db: DB, product_ids: set[str]) -> list[dict]:
    """The documents that go with every sale of these items, each item's together."""
    if not product_ids:
        return []
    docs = db.scalars(select(ProductDocument).where(ProductDocument.product_id.in_(product_ids), ProductDocument.send_with_sales)
                      .order_by(ProductDocument.product_id, ProductDocument.name)).all()
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_({d.product_id for d in docs})))}
    return [{**document_out(d), "product": product_ref(products[d.product_id])} for d in docs]


@router.get("/products/{product_id}/documents")
def list_documents(_: allowed("products.view"), db: DB, product_id: str) -> list[dict]:
    return of_product(db, found(db, Product, product_id, "product").id)


@router.post("/products/{product_id}/documents", status_code=status.HTTP_201_CREATED)
async def add_document(_: allowed("products.edit"), me: CurrentUser, db: DB, product_id: str, file: UploadFile = File(...),
                       name: str = Form("", max_length=120), send_with_sales: bool = Form(True, alias="sendWithSales")) -> list[dict]:
    product = found(db, Product, product_id, "product")
    if file.content_type not in TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use a PDF, a PNG or JPEG picture, or a Word or Excel file.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Keep documents under 5 MB.")
    if len(of_product(db, product.id)) >= PER_PRODUCT:
        raise conflict(f"An item keeps {PER_PRODUCT} documents at most. Remove one first.")
    file_name = (file.filename or "document")[:200]
    d = ProductDocument(product_id=product.id, name=(name.strip() or file_name.rsplit(".", 1)[0])[:120], file_name=file_name,
                        content_type=file.content_type, data=data, size=len(data), send_with_sales=send_with_sales)
    db.add(d)
    db.flush()
    audit(db, me, "product.document_added", target=f"{product.sku} · {d.name}", target_type="product", target_id=product.id)
    db.commit()
    return of_product(db, product.id)


def _doc(db: DB, product_id: str, document_id: str) -> ProductDocument:
    d = found(db, ProductDocument, document_id, "document")
    if d.product_id != product_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That document isn't this item's.")
    return d


@router.get("/products/{product_id}/documents/{document_id}")
def download(_: allowed("orders.view"), db: DB, product_id: str, document_id: str) -> Response:
    d = _doc(db, product_id, document_id)
    safe = d.file_name.replace('"', "")
    return Response(d.data, media_type=d.content_type, headers={"Content-Disposition": f'inline; filename="{safe}"', "Cache-Control": "private, max-age=600"})


class DocumentPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=120)
    send_with_sales: bool | None = None


@router.patch("/products/{product_id}/documents/{document_id}")
def change_document(_: allowed("products.edit"), me: CurrentUser, db: DB, product_id: str, document_id: str, body: DocumentPatch) -> list[dict]:
    d = _doc(db, product_id, document_id)
    fields = {k: v for k, v in changed(body).items() if v is not None and getattr(d, k) != v}
    for k, v in fields.items():
        setattr(d, k, v.strip() if isinstance(v, str) else v)
    if fields:
        audit(db, me, "product.document_changed", target=d.name, target_type="product", target_id=product_id, fields=sorted(fields))
        db.commit()
    return of_product(db, product_id)


@router.delete("/products/{product_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(_: allowed("products.edit"), me: CurrentUser, db: DB, product_id: str, document_id: str) -> Response:
    d = _doc(db, product_id, document_id)
    audit(db, me, "product.document_removed", target=d.name, target_type="product", target_id=product_id)
    db.delete(d)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/orders/{order_id}/documents")
def delivery_documents(_: allowed("orders.view"), db: DB, order_id: str) -> list[dict]:
    o = found(db, Order, order_id, "order")
    return with_sale(db, {line.product_id for line in o.lines})


@router.get("/sales-orders/{order_id}/documents")
def sales_order_documents(_: allowed("sales.view"), db: DB, order_id: str) -> list[dict]:
    o = found(db, SalesOrder, order_id, "sales order")
    return with_sale(db, {line.product_id for line in o.lines})


# --- sending them (step 15e): by email, through the company's Email sending service -------------------

MAX_SEND = 20_000_000


class SendIn(Api):
    to: list[str] = Field(min_length=1, max_length=10)
    message: str | None = Field(None, max_length=2000)


def _send(db: DB, request, me, product_ids: set[str], number: str, recipient: str, body: SendIn, target_type: str, target_id: str) -> dict:
    import re

    from app import mail

    addresses = [a.strip().lower() for a in body.to if a.strip()]
    bad = [a for a in addresses if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", a)]
    if bad or not addresses:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "to"], "msg": "Enter email addresses like name@company.com."}])
    docs = db.scalars(select(ProductDocument).where(ProductDocument.product_id.in_(product_ids), ProductDocument.send_with_sales)
                      .order_by(ProductDocument.name)).all()
    if not docs:
        raise conflict("There are no documents to send with it: add them on its items' pages.")
    if sum(d.size for d in docs) > MAX_SEND:
        raise conflict("Its documents come to more than 20 MB together, too much for one email. Download and send them in parts.")
    text = (body.message.strip() + "\n\n" if body.message and body.message.strip() else "") + \
        f"Please find attached the documents for {number} ({recipient}):\n" + "\n".join(f"- {d.name}" for d in docs)
    try:
        mail.send(request.app.state.settings, getattr(request.state, "company", None), addresses, f"Documents for {number}", text,
                  [(d.file_name, d.content_type, d.data) for d in docs])
    except mail.CantSend as e:
        raise conflict(str(e)) from None
    audit(db, me, "documents.sent", target=f"{number} → {', '.join(addresses)}", target_type=target_type, target_id=target_id, fields=[d.name for d in docs])
    db.commit()
    return {"sent": len(docs), "to": addresses}


@router.post("/orders/{order_id}/documents/send")
def send_delivery_documents(_: allowed("orders.view"), me: CurrentUser, db: DB, order_id: str, body: SendIn, request: Request) -> dict:
    o = found(db, Order, order_id, "order")
    return _send(db, request, me, {line.product_id for line in o.lines}, o.number, o.recipient, body, "order", o.id)


@router.post("/sales-orders/{order_id}/documents/send")
def send_sales_order_documents(_: allowed("sales.view"), me: CurrentUser, db: DB, order_id: str, body: SendIn, request: Request) -> dict:
    o = found(db, SalesOrder, order_id, "sales order")
    return _send(db, request, me, {line.product_id for line in o.lines}, o.number, o.customer_name, body, "sales_order", o.id)
