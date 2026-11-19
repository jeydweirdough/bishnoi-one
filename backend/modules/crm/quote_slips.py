"""Quotes waiting for their team lead, on approval slips (Step 4C, 2026-11-18).

A quote that needs approval for a reason the team lead decides (a discount over the limit, a free-goods offer...)
opens an approval slip on the Platform when the CRM is connected to Bishnoi One (approval.requested, kind "quote"),
signed up the rep's org chart; the slip's end comes back as approval.decided and decides the quote as its last signer,
telling the rep as before. A quote at a requested price is Finance's to approve (routers/integration_prices.py): it
gets no slip and nothing about it changes. Standalone, the team lead decides on the quote, as before.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.crm import business_events
from modules.crm.models import Quote, User

REASONS = {"discount": "Discount over the limit"}


def connected(settings) -> bool:
    """Connected to Bishnoi One (PLATFORM_API_URL): quotes for a team lead are approved on their slip."""
    return bool(getattr(settings, "platform_api_url", None))


def ask(db: Session, settings, quote: Quote, me: User) -> None:
    lines = [{"name": str(line.get("name") or line.get("code") or ""), "quantity": int(line.get("quantity") or 0),
              "freeQuantity": int(line.get("freeQuantity") or 0), "totalCentavos": int(line.get("totalCentavos") or 0)}
             for line in (quote.lines or [])[:30] if isinstance(line, dict)]
    attachments = [{"label": f"Quote {quote.number}", "app": "crm", "kind": "quote", "id": quote.id, "number": quote.number, "url": f"/crm/quotes/{quote.id}"}]
    if quote.rx:
        attachments.append({"label": "Rx check: the quote's prescription", "app": "crm", "kind": "quote", "id": quote.id, "number": quote.number,
                            "url": f"/crm/quotes/{quote.id}"})
    business_events.emit(db, getattr(settings, "company", None), "approval.requested", {
        "kind": "quote", "id": quote.id, "number": quote.number, "title": f"Quote {quote.number} for {quote.customer_name}",
        "url": f"/crm/quotes/{quote.id}",
        "requester": {"identityId": me.platform_identity_id, "email": me.email, "name": me.full_name},
        "summary": {"customer": quote.customer_name, "totalCentavos": quote.total_centavos, "grossCentavos": quote.gross_centavos,
                    "discountCentavos": quote.discount_centavos, "currency": getattr(settings, "org_currency", None) or "PHP",
                    "lines": lines, "moreLines": max(0, len(quote.lines or []) - len(lines)), "notes": quote.notes,
                    "reasons": [REASONS.get(r, r) for r in (quote.approval_reasons or [])]},
        "attachments": attachments,
    })


def withdraw(db: Session, settings, quote: Quote, reason: str, by: str) -> None:
    business_events.emit(db, getattr(settings, "company", None), "approval.withdrawn", {"kind": "quote", "id": quote.id, "reason": reason[:500], "by": by})


def decided(db: Session, data: dict) -> None:
    """The slip's end: the quote approved or rejected as its last signer, the rep told as before."""
    from modules.crm import mail
    from modules.crm.audit import audit
    from modules.crm.routers.quotes import Decision, apply_decision, finance_decides

    quote = db.get(Quote, str(data.get("id") or ""))
    if quote is None or quote.approval_status != "pending" or finance_decides(quote):
        return
    by = data.get("by") or {}
    user = db.scalar(select(User).where(User.platform_identity_id == str(by.get("identityId") or ""))) if by.get("identityId") else None
    if user is None and by.get("email"):
        user = db.scalar(select(User).where(func.lower(User.email) == str(by["email"]).lower()))
    name = user.full_name if user else str(by.get("name") or "An approver")
    slip = str((data.get("approval") or {}).get("number") or "")
    if data.get("decision") == "approved":
        body = Decision(decision="approve", note=data.get("note") or None)
    elif data.get("decision") == "returned":
        body = Decision(decision="reject", note=(f"{data.get('note') or 'Returned'} ({slip})" if slip else data.get("note")) or "Returned")
    else:
        return
    apply_decision(quote, body, by_id=user.id if user else None, by_name=name)
    audit(db, user or name, f"quote.{quote.approval_status}", target=quote.number, target_type="quote", target_id=quote.id, fields=[slip] if slip else [])
    settings = business_events._state.get("settings")
    if settings is not None:
        try:
            mail.quote_decided(db, settings, quote, name, user.id if user else None)
        except Exception:  # noqa: BLE001 (telling the rep by email never undoes the decision)
            pass
