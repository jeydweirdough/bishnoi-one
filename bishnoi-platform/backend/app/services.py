"""Outside services a company's applications connect to (Zoho Books, the email
providers), and what each one needs. Kept here, per company, so no application
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

# The email providers: the company registers the CRM with each once (here); each
# person then connects their own mailbox in the CRM (Account → Mailbox).
REDIRECT_HINT = "When registering the CRM with them, give this as the redirect address: the CRM's address followed by /account/mailbox/callback."

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
    Service(
        key="gmail",
        name="Gmail (Google Workspace)",
        purpose="Each person sends from their own Gmail address in the CRM, and every email sent is kept on the customer.",
        help_url="https://developers.google.com/workspace/guides/create-credentials#oauth-client-id",
        apps=("crm",),
        details=(
            Detail("client_id", "Client ID", "Google Cloud console → APIs and services → Credentials → OAuth client (web application). Turn on the Gmail API. " + REDIRECT_HINT),
            Detail("client_secret", "Client secret", "Shown beside the Client ID.", secret=True),
        ),
    ),
    Service(
        key="outlook",
        name="Outlook (Microsoft 365)",
        purpose="Each person sends from their own Outlook address in the CRM, and every email sent is kept on the customer.",
        help_url="https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app",
        apps=("crm",),
        details=(
            Detail("tenant_id", "Directory (tenant) ID", "Microsoft Entra admin centre → App registrations → the CRM's app → Overview."),
            Detail("client_id", "Application (client) ID", "On the same page. Give it the Mail.Send and User.Read permissions. " + REDIRECT_HINT),
            Detail("client_secret", "Client secret", "Certificates and secrets → New client secret: copy its value.", secret=True),
        ),
    ),
    Service(
        key="zoho_mail",
        name="Zoho Mail",
        purpose="Each person sends from their own Zoho Mail address in the CRM, and every email sent is kept on the customer.",
        help_url="https://www.zoho.com/mail/help/api/using-oauth-2.html",
        apps=("crm",),
        details=(
            Detail("data_centre", "Data centre", "Where your Zoho account is: the end of the address you sign in at.", options=ZOHO_CENTRES),
            Detail("client_id", "Client ID", "api-console.zoho.com → Add client → Server-based application. " + REDIRECT_HINT),
            Detail("client_secret", "Client secret", "Shown beside the Client ID.", secret=True),
        ),
    ),
    # The CRM's lead inbox: each channel calls the CRM's address for it,
    # <CRM API address>/hooks/<channel>?company=<this company's short name>
    # (the CRM's Lead inbox page shows each one, ready to copy).
    Service(
        key="facebook",
        name="Facebook (lead forms and Messenger)",
        purpose="Answers to the page's lead forms, and Messenger messages to the page, arrive in the CRM's lead inbox.",
        help_url="https://developers.facebook.com/docs/graph-api/webhooks/getting-started",
        apps=("crm",),
        details=(
            Detail("page_id", "Page ID", "The Facebook page's ID: the page → About → Page transparency, or Meta Business Suite → Settings."),
            Detail("app_secret", "App secret", "developers.facebook.com → your app → App settings → Basic. Facebook signs each call with it.", secret=True),
            Detail("verify_token", "Verify token", "Any long random text. Type the same in the app's Webhooks settings (product Page, fields leadgen and messages), with the CRM's address /hooks/facebook.", secret=True),
            Detail("page_access_token", "Page access token", "A long-lived page token with leads_retrieval, pages_messaging and pages_manage_metadata, so the CRM can read each form's answers.", secret=True),
        ),
    ),
    Service(
        key="whatsapp",
        name="WhatsApp Business",
        purpose="Messages to the company's WhatsApp number arrive in the CRM's lead inbox.",
        help_url="https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks",
        apps=("crm",),
        details=(
            Detail("phone_number_id", "Phone number ID", "developers.facebook.com → your app → WhatsApp → API setup: the ID under the number."),
            Detail("app_secret", "App secret", "App settings → Basic. Meta signs each call with it.", secret=True),
            Detail("verify_token", "Verify token", "Any long random text. Type the same in WhatsApp → Configuration → Webhook, with the CRM's address /hooks/whatsapp, and subscribe to messages.", secret=True),
        ),
    ),
    Service(
        key="viber",
        name="Viber",
        purpose="Messages to the company's Viber bot arrive in the CRM's lead inbox.",
        help_url="https://developers.viber.com/docs/api/rest-bot-api/",
        apps=("crm",),
        details=(
            Detail("auth_token", "Authentication token", "partners.viber.com → your bot account → Info. Then set the webhook to the CRM's address /hooks/viber.", secret=True),
        ),
    ),
    Service(
        key="tawkto",
        name="Tawk.to",
        purpose="Chats and tickets from the website's Tawk.to box arrive in the CRM's lead inbox.",
        help_url="https://help.tawk.to/article/using-webhooks",
        apps=("crm",),
        details=(
            Detail("webhook_secret", "Webhook secret", "Tawk.to → Administration → Settings → Webhooks → Create: the CRM's address /hooks/tawkto, events Chat start and New ticket. Copy its secret key here.", secret=True),
        ),
    ),
    Service(
        key="web_forms",
        name="Website forms, Make and Zapier",
        purpose="Enquiries sent by the website's own forms, or by Make or Zapier, arrive in the CRM's lead inbox.",
        help_url="https://www.make.com/en/help/tools/http",
        apps=("crm",),
        details=(
            Detail("form_key", "Form key", "Any long random text. The website or tool sends it in the X-Bishnoi-Key header with each enquiry (name, business, phone, email, city, message) to the CRM's address /hooks/form.", secret=True),
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
