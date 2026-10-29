"""Sending email from Inventory (feature plan step 15e, 2026-10-29): a sale's documents to the customer.

It sends through the company's Email sending service on the Platform (Admin Console → Integrations → Email
sending: Brevo or any SMTP service), asked for with this application's connect key (GET /connect/services),
the same service the CRM sends through. Without it, sending says so in words a person can act on.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx

from app.config import Settings
from app.platform_connect import connect_key

log = logging.getLogger("inventory.mail")


class CantSend(Exception):
    """Why an email couldn't go, in plain words."""


@dataclass
class Relay:
    host: str
    port: int
    username: str | None
    password: str | None
    sender: str


def relay(settings: Settings, company: str | None) -> Relay:
    """The company's SMTP service from the Platform."""
    key = connect_key(settings) if settings.platform_api_url else None
    if not settings.platform_api_url or not key:
        raise CantSend("Inventory isn't connected to Bishnoi One, so it has no email service to send with.")
    try:
        r = httpx.get(f"{settings.platform_api_url.rstrip('/')}/connect/services", params={"company": company or ""},
                      headers={"X-Bishnoi-App-Key": key}, timeout=8)
    except httpx.HTTPError as e:
        raise CantSend("Bishnoi One can't be reached right now. Try again in a moment.") from e
    found = (r.json().get("services") or {}).get("smtp") if r.status_code == 200 else None
    if not found or not found.get("host"):
        raise CantSend("Your company hasn't set up email sending. Its administrator turns it on in the Admin Console: Integrations, Email sending.")
    try:
        port = int(found.get("port") or 587)
    except ValueError:
        port = 587
    return Relay(found["host"], port, found.get("username"), found.get("password"), found.get("from_email") or found.get("username") or "")


def send(settings: Settings, company: str | None, to: list[str], subject: str, text: str, attachments: list[tuple[str, str, bytes]]) -> None:
    """One email to each address, with the attachments (file name, content type, bytes)."""
    via = relay(settings, company)
    try:
        with smtplib.SMTP(via.host, via.port, timeout=30) as smtp:
            smtp.starttls()
            if via.username and via.password:
                smtp.login(via.username, via.password)
            for address in to:
                message = EmailMessage()
                message["From"] = formataddr((settings.org_name, via.sender))
                message["To"] = address
                message["Subject"] = subject
                message["Message-ID"] = make_msgid(domain=via.sender.rpartition("@")[2] or None)
                message.set_content(text)
                for name, kind, data in attachments:
                    main, _, sub = kind.partition("/")
                    message.add_attachment(data, maintype=main or "application", subtype=sub or "octet-stream", filename=name)
                smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as e:
        raise CantSend("The email service didn't accept its login. Check Email sending in the Admin Console.") from e
    except (smtplib.SMTPException, OSError) as e:
        log.error("Mail: sending failed (%s).", e.__class__.__name__)
        raise CantSend("The email couldn't be sent. Try again, or check Email sending in the Admin Console.") from e
