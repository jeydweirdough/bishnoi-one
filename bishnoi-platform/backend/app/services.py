"""Outside services a company's applications connect to (Zoho Books, email
sending), and what each one needs. Kept here, per company, so no application
keeps a key of its own for them: a Platform Admin fills them in on the
company's Connections tab, and each application asks for its company's
(GET /connect/services, with its connect key).

A detail marked secret is kept encrypted with a key worked out from the
platform's signing key, and never sent back to a screen: the screen only learns
that one is saved, and its last four characters. Only the applications that
use a service are given it.

Add a service by adding it to SERVICES (and, to test it, a checker in CHECKS).
"""

import base64
import hashlib
import json
from dataclasses import dataclass, field

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app import passes
from app.config import Settings


@dataclass(frozen=True)
class Detail:
    key: str
    label: str
    hint: str = ""
    secret: bool = False
    required: bool = True
    options: tuple[tuple[str, str], ...] = ()  # (value, label): a pick list


@dataclass(frozen=True)
class Service:
    key: str
    name: str
    purpose: str
    help_url: str
    # The applications that use it, by key: only they are given its details.
    apps: tuple[str, ...]
    details: tuple[Detail, ...] = field(default_factory=tuple)


ZOHO_CENTRES = (
    ("com", "United States (zoho.com)"),
    ("in", "India (zoho.in)"),
    ("eu", "Europe (zoho.eu)"),
    ("com.au", "Australia (zoho.com.au)"),
    ("jp", "Japan (zoho.jp)"),
    ("ca", "Canada (zohocloud.ca)"),
    ("sa", "Saudi Arabia (zoho.sa)"),
    ("com.cn", "China (zoho.com.cn)"),
)

SERVICES: tuple[Service, ...] = (
    Service(
        key="zoho_books",
        name="Zoho Books",
        purpose="Invoices under each customer's name, for the monthly rebate, and registering the rebate back in Zoho.",
        help_url="https://www.zoho.com/books/api/v3/oauth/",
        apps=("crm",),
        details=(
            Detail("data_centre", "Data centre", "Where your Zoho account is: the end of the address you sign in at.", options=ZOHO_CENTRES),
            Detail("organization_id", "Organization ID", "Zoho Books → Settings → Organization profile, or the number in the Books address."),
            Detail("client_id", "Client ID", "From api-console.zoho.com: add a Self Client (or a server-based app) and copy its Client ID."),
            Detail("client_secret", "Client secret", "Shown beside the Client ID in the API console.", secret=True),
            Detail(
                "refresh_token",
                "Refresh token",
                "Made in the API console from a grant code with the scope ZohoBooks.fullaccess.all. It lets the CRM sign in to Zoho without a password.",
                secret=True,
            ),
            Detail(
                "webhook_secret",
                "Webhook secret",
                "Optional. Any long random text, also typed into Zoho Books → Settings → Webhooks, so the CRM can tell Zoho's calls are genuine.",
                secret=True,
                required=False,
            ),
        ),
    ),
    # The CRM's own emails (quotes waiting for approval, price approvals): sent
    # through the company's email delivery service, set here instead of on the
    # CRM's server (decided 2026-10-27). SMTP_* on the server still wins.
    Service(
        key="smtp",
        name="Email sending (Brevo or any SMTP service)",
        purpose="The CRM's own emails (quotes waiting for approval, price approvals, notices) and Inventory's (a sale's documents to the customer).",
        help_url="https://help.brevo.com/hc/en-us/articles/7924908994450",
        apps=("crm", "inventory"),  # Inventory sends a sale's documents to the customer (step 15e, 2026-10-29)
        details=(
            Detail("host", "SMTP server", "Brevo: smtp-relay.brevo.com. Another service: its SMTP server's address."),
            Detail("port", "Port", "587 for almost every service (Brevo too).", required=False),
            Detail("username", "Login", "Brevo → SMTP and API → SMTP: the login shown there (it ends in @smtp-brevo.com)."),
            Detail("password", "SMTP key", "On the same page: Generate a new SMTP key (it starts xsmtpsib-). Not the API key.", secret=True),
            Detail("from_email", "Sent from", "An address the service has verified, e.g. crm@getmeds.ph (Brevo → Senders, domains and dedicated IPs)."),
        ),
    ),
)

BY_KEY = {s.key: s for s in SERVICES}


# --- keeping secrets ---


def _box(settings: Settings) -> Fernet:
    raw = passes._raw_private(passes.signing_key(settings))
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"bishnoi-services:" + raw).digest()))


def seal(settings: Settings, secrets: dict[str, str]) -> str | None:
    return _box(settings).encrypt(json.dumps(secrets).encode()).decode() if secrets else None


def unseal(settings: Settings, sealed: str | None) -> dict[str, str] | None:
    """The saved secrets ({} when there are none), or None when they were sealed with another signing key."""
    if not sealed:
        return {}
    try:
        return json.loads(_box(settings).decrypt(sealed.encode()))
    except (InvalidToken, ValueError):
        return None


def missing(service: Service, values: dict, secrets: dict) -> list[str]:
    """The required details not filled in yet, by label."""
    return [d.label for d in service.details if d.required and not (secrets.get(d.key) if d.secret else values.get(d.key))]


def ending(secret: str) -> str:
    """The last four characters of a long secret, to tell which one is saved. Short ones show nothing."""
    return secret[-4:] if len(secret) >= 12 else ""


# --- testing a connection ---


class CheckFailed(Exception):
    pass


def zoho_hosts(centre: str) -> tuple[str, str]:
    """Zoho's sign-in and API addresses for a data centre."""
    if centre == "ca":
        return "https://accounts.zohocloud.ca", "https://www.zohoapis.ca"
    return f"https://accounts.zoho.{centre}", f"https://www.zohoapis.{centre}"


def check_zoho_books(details: dict[str, str]) -> str:
    """Signs in to Zoho with the refresh token, then finds the organization.
    Returns what it found; raises CheckFailed with what went wrong."""
    accounts, api = zoho_hosts(details.get("data_centre") or "com")
    try:
        token = httpx.post(
            f"{accounts}/oauth/v2/token",
            data={
                "refresh_token": details.get("refresh_token", ""),
                "client_id": details.get("client_id", ""),
                "client_secret": details.get("client_secret", ""),
                "grant_type": "refresh_token",
            },
            timeout=15,
        ).json()
        if "access_token" not in token:
            raise CheckFailed(f"Zoho didn't accept the client ID, secret and refresh token ({token.get('error', 'no reason given')}).")
        orgs = httpx.get(f"{api}/books/v3/organizations", headers={"Authorization": f"Zoho-oauthtoken {token['access_token']}"}, timeout=15).json()
    except httpx.HTTPError as e:
        raise CheckFailed(f"Couldn't reach Zoho ({type(e).__name__}). Check the data centre.") from None
    except ValueError:
        raise CheckFailed("Zoho answered with something that isn't JSON. Check the data centre.") from None
    wanted = details.get("organization_id", "")
    for org in orgs.get("organizations", []):
        if str(org.get("organization_id")) == wanted:
            return f"Connected to {org.get('name', 'the organization')}."
    raise CheckFailed("Signed in to Zoho, but no organization there has that Organization ID.")


def check_smtp(details: dict[str, str]) -> str:
    """Signs in to the SMTP server with the login and key; sends nothing."""
    import smtplib

    try:
        with smtplib.SMTP(details.get("host", ""), int(details.get("port") or 587), timeout=15) as smtp:
            smtp.starttls()
            smtp.login(details.get("username", ""), details.get("password", ""))
    except smtplib.SMTPAuthenticationError:
        raise CheckFailed("The server didn't accept the login and SMTP key.") from None
    except (OSError, smtplib.SMTPException, ValueError) as e:
        raise CheckFailed(f"Couldn't reach the SMTP server ({type(e).__name__}). Check its address and port.") from None
    return "Signed in to the SMTP server."


CHECKS = {"zoho_books": check_zoho_books, "smtp": check_smtp}
