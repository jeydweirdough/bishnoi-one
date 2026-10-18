"""Email notifications: sent, not only shown on a screen.

Mail goes out through an email delivery service's SMTP server (its host,
port, user name and password in the settings); nothing is hosted here.

Switches, as with Discord (app/discord.py):
    EMAIL_ENABLED  true, or nothing is sent
    EMAIL_MODE     smtp = really send; mock = keep it on this machine (logged,
                   and kept in OUTBOX for the tests)

Sending happens on a thread of its own, so a slow mail server never holds up
the request that caused it, and a failed send is logged, never raised.

Every email has the same plain layout (the way mjml lays mail out, by hand):
a 600px table with inline styles, which Outlook and Gmail both draw properly,
and a text version for mail apps that show no HTML.
"""

from __future__ import annotations

import html
import logging
import smtplib
import threading
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import permissions_of
from app.config import Settings
from app.models import Quote, User

log = logging.getLogger("bishnoi.mail")

BRAND = "#1F3864"


@dataclass
class Sent:
    to: list[str]
    subject: str
    text: str
    html: str


# What mock mode "sent", newest last. The tests read it.
OUTBOX: list[Sent] = []


def layout(heading: str, lines: list[str], button: tuple[str, str] | None, org: str) -> tuple[str, str]:
    """(HTML, text) for an email: a heading, a few short lines, maybe one button."""
    e = html.escape
    body = "".join(f'<p style="margin:0 0 12px;font-size:15px;line-height:22px;color:#1d2433">{e(line)}</p>' for line in lines)
    action = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 4px"><tr><td style="background:{BRAND};border-radius:4px">'
        f'<a href="{e(button[1])}" style="display:inline-block;padding:10px 18px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none">{e(button[0])}</a>'
        "</td></tr></table>"
        if button
        else ""
    )
    page = (
        '<!doctype html><html><body style="margin:0;padding:0;background:#f3f4f6">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #e5e7eb;border-radius:6px">'
        f'<tr><td style="padding:14px 24px;border-bottom:3px solid {BRAND};font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;color:{BRAND}">{e(org)} CRM</td></tr>'
        f'<tr><td style="padding:22px 24px 18px;font-family:Arial,Helvetica,sans-serif">'
        f'<h1 style="margin:0 0 14px;font-size:19px;line-height:26px;color:#111827">{e(heading)}</h1>{body}{action}</td></tr>'
        '<tr><td style="padding:12px 24px;border-top:1px solid #e5e7eb;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#6b7280">'
        "Sent by the CRM because of your role. Your administrator decides who gets these.</td></tr>"
        "</table></td></tr></table></body></html>"
    )
    text = "\n\n".join([heading, *lines, *([f"{button[0]}: {button[1]}"] if button else [])])
    return page, text


def send(settings: Settings, to: list[str], subject: str, heading: str, lines: list[str], button: tuple[str, str] | None = None) -> None:
    """Sends one email to each address (never one email to all: people's
    addresses aren't shown to each other). Does nothing while switched off."""
    to = sorted({a for a in to if a})
    if not settings.email_enabled or not to:
        return
    page, text = layout(heading, lines, button, settings.org_name)
    if settings.email_mode != "smtp":
        OUTBOX.append(Sent(to=to, subject=subject, text=text, html=page))
        log.info("email (mock) to %d: %s", len(to), subject)
        return
    threading.Thread(target=_deliver, args=(settings, to, subject, text, page), daemon=True).start()


def _deliver(settings: Settings, to: list[str], subject: str, text: str, page: str) -> None:
    sender = settings.email_from or settings.smtp_username or ""
    try:
        with smtplib.SMTP(settings.smtp_host or "", settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            for address in to:
                message = EmailMessage()
                message["From"] = formataddr((f"{settings.org_name} CRM", sender))
                message["To"] = address
                message["Subject"] = subject
                message["Message-ID"] = make_msgid(domain=sender.rpartition("@")[2] or None)
                message.set_content(text)
                message.add_alternative(page, subtype="html")
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        # Never the password; the server's own words are enough to fix it.
        log.warning("email not sent (%s): %s", subject, error.__class__.__name__ + ": " + str(error)[:200])


def link(settings: Settings, path: str) -> tuple[str, str] | None:
    return ("Open in the CRM", settings.crm_app_url.rstrip("/") + path) if settings.crm_app_url else None


# --- what's sent ----------------------------------------------------------------------------

# Why a quote waits for approval (app/pricing.py), in words.
REASONS = {"discount": "a discount above the limit", "price": "a price type that needs approval", "asked": "the customer asking for another price"}


def approvers_of(db: Session, quote: Quote) -> list[User]:
    """Who decides on this quote: the team's approvers (a role reaching the
    team, with Quotes → Approve); with none in the team, those who reach every
    team. Never the person who made it."""
    people = [u for u in db.scalars(select(User).where(User.is_active)) if "quotes.approve" in permissions_of(u.role) and u.id != quote.owner_id]
    team = [u for u in people if u.role.scope == "team" and quote.team_id and quote.team_id in u.all_team_ids]
    # No team lead to decide: the team's manager, then those who reach every team.
    managers = [u for u in people if u.role.scope == "managed" and quote.team_id in {t.id for t in u.managed_teams} | (u.all_team_ids)]
    return team or managers or [u for u in people if u.role.scope == "all"]


def quote_waiting(db: Session, settings: Settings, quote: Quote, maker: User) -> None:
    reasons = "; ".join(REASONS.get(r, r) for r in quote.approval_reasons or []) or "it's outside the usual limits"
    send(
        settings,
        [u.email for u in approvers_of(db, quote)],
        f"Quote {quote.number} is waiting for your approval",
        f"Quote {quote.number} needs your approval",
        [f"{maker.full_name} made it for {quote_for(quote)}.", f"It needs approval for {reasons}."],
        link(settings, f"/quotes/{quote.id}"),
    )


def quote_decided(db: Session, settings: Settings, quote: Quote, decider_name: str, decider_id: str | None = None) -> None:
    """decider_id: None when Finance decided, in its own app."""
    owner = db.get(User, quote.owner_id)
    if owner is None or owner.id == decider_id or not owner.is_active:
        return
    approved = quote.approval_status == "approved"
    lines = [f"{decider_name} {'approved' if approved else 'rejected'} your quote for {quote_for(quote)}."]
    if quote.approval_note:
        lines.append(f"{'Their note' if approved else 'Why'}: {quote.approval_note}")
    send(
        settings,
        [owner.email],
        f"Quote {quote.number} was {'approved' if approved else 'rejected'}",
        f"Quote {quote.number} was {'approved' if approved else 'rejected'}",
        lines,
        link(settings, f"/quotes/{quote.id}"),
    )


def quote_for(quote: Quote) -> str:
    return quote.customer_name or "a customer"
