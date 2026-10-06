"""Outside services the CRM may connect to, and what each one needs.

An administrator fills these in under Settings → Connections. A field marked
secret is kept encrypted with CONNECTIONS_KEY and never sent back to a screen:
the screen only learns that one is saved, and its last four characters.

Zoho Books comes first: the doctors' monthly rebate is worked out from the
invoices there. Add a service by adding it to SERVICES (and, to test it, a
checker in CHECKS).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.config import DATA_DIR, Settings


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
)

# The email providers: the company registers the CRM with each once (here); each
# person then connects their own mailbox (app/mailbox.py). The address to give
# the provider when registering is CRM_APP_URL + /account/mailbox/callback.
REDIRECT_HINT = "When registering the CRM with them, give this as the redirect address: your CRM's address followed by /account/mailbox/callback."

SERVICES = SERVICES + (
    Service(
        key="gmail",
        name="Gmail (Google Workspace)",
        purpose="Each person sends from their own Gmail address, and every email sent is kept on the customer.",
        help_url="https://developers.google.com/workspace/guides/create-credentials#oauth-client-id",
        details=(
            Detail("client_id", "Client ID", "Google Cloud console → APIs and services → Credentials → OAuth client (web application). Turn on the Gmail API. " + REDIRECT_HINT),
            Detail("client_secret", "Client secret", "Shown beside the Client ID.", secret=True),
        ),
    ),
    Service(
        key="outlook",
        name="Outlook (Microsoft 365)",
        purpose="Each person sends from their own Outlook address, and every email sent is kept on the customer.",
        help_url="https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app",
        details=(
            Detail("tenant_id", "Directory (tenant) ID", "Microsoft Entra admin centre → App registrations → the CRM's app → Overview."),
            Detail("client_id", "Application (client) ID", "On the same page. Give it the Mail.Send and User.Read permissions. " + REDIRECT_HINT),
            Detail("client_secret", "Client secret", "Certificates and secrets → New client secret: copy its value.", secret=True),
        ),
    ),
    Service(
        key="zoho_mail",
        name="Zoho Mail",
        purpose="Each person sends from their own Zoho Mail address, and every email sent is kept on the customer.",
        help_url="https://www.zoho.com/mail/help/api/using-oauth-2.html",
        details=(
            Detail("data_centre", "Data centre", "Where your Zoho account is: the end of the address you sign in at.", options=ZOHO_CENTRES),
            Detail("client_id", "Client ID", "api-console.zoho.com → Add client → Server-based application. " + REDIRECT_HINT),
            Detail("client_secret", "Client secret", "Shown beside the Client ID.", secret=True),
        ),
    ),
)
# Ready once filled in: each person's own sign-in is the real test.
MAIL_PROVIDERS = ("gmail", "outlook", "zoho_mail")

BY_KEY = {s.key: s for s in SERVICES}


# --- keeping secrets ---


class NoKey(Exception):
    """There's no CONNECTIONS_KEY to encrypt with (production without one set)."""


def _fernet(settings: Settings) -> Fernet:
    if settings.connections_key:
        return Fernet(settings.connections_key.get_secret_value().encode())
    if settings.is_production:
        raise NoKey("Set CONNECTIONS_KEY on the server before saving a connection.")
    # Development: a key of its own, made once, beside the database.
    path: Path = DATA_DIR / "connections.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Fernet.generate_key())
    return Fernet(path.read_bytes().strip())


def seal(settings: Settings, secrets: dict[str, str]) -> str | None:
    return _fernet(settings).encrypt(json.dumps(secrets).encode()).decode() if secrets else None


def unseal(settings: Settings, sealed: str | None) -> dict[str, str]:
    """The saved secrets; none when there are none, or when the key they were saved with is gone."""
    if not sealed:
        return {}
    try:
        return json.loads(_fernet(settings).decrypt(sealed.encode()))
    except (InvalidToken, NoKey, ValueError):
        return {}


def missing(service: Service, values: dict, secrets: dict) -> list[str]:
    """The required details not filled in yet, by label."""
    return [d.label for d in service.details if d.required and not (secrets.get(d.key) if d.secret else values.get(d.key))]


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
        raise CheckFailed(f"Couldn't reach Zoho ({type(e).__name__}). Check the data centre and this server's internet.") from None
    except ValueError:
        raise CheckFailed("Zoho answered with something that isn't JSON. Check the data centre.") from None
    wanted = details.get("organization_id", "")
    for org in orgs.get("organizations", []):
        if str(org.get("organization_id")) == wanted:
            return f"Connected to {org.get('name', 'the organization')}."
    raise CheckFailed("Signed in to Zoho, but no organization there has that Organization ID.")


CHECKS = {"zoho_books": check_zoho_books}
