"""Each person's own mailbox, to send email from the CRM (HubSpot's connected
inbox, C7).

Gmail, Outlook and Zoho Mail are connected by the person's own sign-in with
the provider (OAuth): the CRM is registered with each provider once, in
Settings → Connections; the person signs in and allows sending, and the CRM
keeps the refresh token it's given, encrypted. Any other provider connects by
SMTP: server, port, user name and password, the password encrypted too.

The CRM never reads the mailbox: it only sends. What it sends is kept on the
customer as an email activity (app/routers/mailbox.py).
"""

import base64
import json
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from urllib.parse import urlencode

import httpx
from cryptography.fernet import InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import connections as svc
from app.config import Settings
from app.models import Connection, Mailbox

REDIRECT_PATH = "/account/mailbox/callback"
STATE_MINUTES = 15


class MailboxError(Exception):
    """Something to tell the person, in their words."""


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    scope: str


PROVIDERS = {
    "gmail": Provider("gmail", "Gmail", "openid email https://www.googleapis.com/auth/gmail.send"),
    "outlook": Provider("outlook", "Outlook", "offline_access openid email User.Read Mail.Send"),
    "zoho_mail": Provider("zoho_mail", "Zoho Mail", "ZohoMail.messages.CREATE,ZohoMail.accounts.READ"),
}


def registration(db: Session, settings: Settings, key: str) -> dict | None:
    """The company's registration with a provider (Settings → Connections), if it's switched on and filled in."""
    row = db.get(Connection, key)
    if row is None or not row.is_enabled:
        return None
    details = {**(row.values or {}), **svc.unseal(settings, row.secrets)}
    return details if not svc.missing(svc.BY_KEY[key], row.values or {}, svc.unseal(settings, row.secrets)) else None


def redirect_uri(settings: Settings) -> str:
    if not settings.crm_app_url:
        raise MailboxError("Set CRM_APP_URL on the server (the CRM's own address) before connecting mailboxes.")
    return settings.crm_app_url.rstrip("/") + REDIRECT_PATH


def _zoho(centre: str) -> tuple[str, str]:
    """Zoho's sign-in and mail API addresses for a data centre."""
    accounts, _ = svc.zoho_hosts(centre or "com")
    mail = "https://mail.zohocloud.ca" if centre == "ca" else f"https://mail.zoho.{centre or 'com'}"
    return accounts, mail


def _endpoints(key: str, reg: dict) -> tuple[str, str]:
    """Where to send the person to sign in, and where to trade the code for tokens."""
    if key == "gmail":
        return "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token"
    if key == "outlook":
        base = f"https://login.microsoftonline.com/{reg['tenant_id']}/oauth2/v2.0"
        return f"{base}/authorize", f"{base}/token"
    accounts, _ = _zoho(reg.get("data_centre", "com"))
    return f"{accounts}/oauth/v2/auth", f"{accounts}/oauth/v2/token"


# --- signing in -------------------------------------------------------------------------------


def state_for(settings: Settings, user_id: str, key: str) -> str:
    """Who asked and for which provider, sealed, so the callback can't be forged or replayed for long."""
    return svc._fernet(settings).encrypt(json.dumps({"u": user_id, "p": key, "t": int(time.time())}).encode()).decode()


def read_state(settings: Settings, state: str) -> tuple[str, str]:
    try:
        data = json.loads(svc._fernet(settings).decrypt(state.encode(), ttl=STATE_MINUTES * 60))
    except (InvalidToken, ValueError, svc.NoKey):
        raise MailboxError("That sign-in took too long or didn't come from here. Try connecting again.") from None
    return data["u"], data["p"]


def sign_in_url(db: Session, settings: Settings, user_id: str, key: str) -> str:
    reg = registration(db, settings, key)
    if reg is None:
        raise MailboxError(f"{PROVIDERS[key].name} isn't set up for the company yet. An administrator sets it up in Settings → Connections.")
    auth, _ = _endpoints(key, reg)
    params = {
        "client_id": reg["client_id"],
        "redirect_uri": redirect_uri(settings),
        "response_type": "code",
        "scope": PROVIDERS[key].scope,
        "state": state_for(settings, user_id, key),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{auth}?{urlencode(params)}"


def _post_token(token_url: str, data: dict) -> dict:
    try:
        answer = httpx.post(token_url, data=data, timeout=15).json()
    except (httpx.HTTPError, ValueError):
        raise MailboxError("Couldn't reach the provider to sign in. Try again in a moment.") from None
    if "access_token" not in answer:
        raise MailboxError(f"The provider didn't accept the sign-in ({answer.get('error_description') or answer.get('error') or 'no reason given'}).")
    return answer


def finish_sign_in(db: Session, settings: Settings, user_id: str, key: str, code: str) -> Mailbox:
    """Trades the provider's code for tokens, finds the address, and keeps the mailbox."""
    reg = registration(db, settings, key)
    if reg is None:
        raise MailboxError(f"{PROVIDERS[key].name} isn't set up for the company any more.")
    _, token_url = _endpoints(key, reg)
    tokens = _post_token(token_url, {
        "grant_type": "authorization_code", "code": code, "client_id": reg["client_id"],
        "client_secret": reg["client_secret"], "redirect_uri": redirect_uri(settings),
    })
    if not tokens.get("refresh_token"):
        raise MailboxError("The provider didn't let the CRM keep sending for you. Disconnect the CRM in your account's security settings and connect again.")
    address, values = _whoami(key, reg, tokens["access_token"])
    box = account(db, user_id, address)
    box.provider, box.address, box.values, box.last_error = key, address, values, None
    box.secrets = svc.seal(settings, {"refresh_token": tokens["refresh_token"]})
    db.add(box)
    return box


def _whoami(key: str, reg: dict, token: str) -> tuple[str, dict]:
    try:
        if key == "gmail":
            me = httpx.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {token}"}, timeout=15).json()
            return me["email"], {}
        if key == "outlook":
            me = httpx.get("https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"Bearer {token}"}, timeout=15).json()
            return me.get("mail") or me["userPrincipalName"], {}
        _, mail = _zoho(reg.get("data_centre", "com"))
        found = httpx.get(f"{mail}/api/accounts", headers={"Authorization": f"Zoho-oauthtoken {token}"}, timeout=15).json()["data"][0]
        return found["primaryEmailAddress"], {"account_id": str(found["accountId"]), "data_centre": reg.get("data_centre", "com")}
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        raise MailboxError("Signed in, but couldn't read your email address from the provider.") from None


def account(db: Session, user_id: str, address: str) -> Mailbox:
    """The person's mailbox at this address (signing in again replaces its tokens), or a new one.
    The first one a person connects is their default."""
    found = db.scalar(select(Mailbox).where(Mailbox.user_id == user_id, func.lower(Mailbox.address) == address.lower()))
    if found is not None:
        return found
    first = db.scalar(select(func.count()).select_from(Mailbox).where(Mailbox.user_id == user_id)) == 0
    return Mailbox(user_id=user_id, address=address, is_default=first)


def mailboxes(db: Session, user_id: str) -> list[Mailbox]:
    return list(db.scalars(select(Mailbox).where(Mailbox.user_id == user_id).order_by(Mailbox.is_default.desc(), Mailbox.address)))


def connect_smtp(db: Session, settings: Settings, user_id: str, d: dict) -> Mailbox:
    """Any other provider: tried once with a sign-in to the server, then kept."""
    try:
        with _smtp(d["host"], d["port"], d["security"]) as server:
            server.login(d["username"], d["password"])
    except (OSError, smtplib.SMTPException) as e:
        raise MailboxError(f"Couldn't sign in to {d['host']} ({type(e).__name__}). Check the server, port, user name and password.") from None
    box = account(db, user_id, d["address"])
    box.provider, box.address, box.last_error = "smtp", d["address"], None
    box.values = {"host": d["host"], "port": d["port"], "security": d["security"], "username": d["username"]}
    box.secrets = svc.seal(settings, {"password": d["password"]})
    db.add(box)
    return box


def _smtp(host: str, port: int, security: str):
    if security == "ssl":
        return smtplib.SMTP_SSL(host, port, timeout=20)
    server = smtplib.SMTP(host, port, timeout=20)
    if security == "starttls":
        server.starttls()
    return server


# --- sending -----------------------------------------------------------------------------------


def _message(sender: str, name: str, to: list[str], subject: str, text: str, html_body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((name, sender))
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid()
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    return msg


def send(db: Session, settings: Settings, box: Mailbox, name: str, to: list[str], subject: str, text: str, html_body: str) -> None:
    """Sends from the person's mailbox; raises MailboxError with what went wrong (also kept on the mailbox)."""
    secrets = svc.unseal(settings, box.secrets)
    try:
        if box.provider == "smtp":
            v = box.values
            with _smtp(v["host"], int(v["port"]), v["security"]) as server:
                server.login(v["username"], secrets["password"])
                server.send_message(_message(box.address, name, to, subject, text, html_body))
            return
        reg = registration(db, settings, box.provider)
        if reg is None or not secrets.get("refresh_token"):
            raise MailboxError("Your mailbox needs connecting again (Account → Mailbox).")
        _, token_url = _endpoints(box.provider, {**reg, **box.values})
        token = _post_token(token_url, {"grant_type": "refresh_token", "refresh_token": secrets["refresh_token"], "client_id": reg["client_id"], "client_secret": reg["client_secret"]})["access_token"]
        if box.provider == "gmail":
            raw = base64.urlsafe_b64encode(_message(box.address, name, to, subject, text, html_body).as_bytes()).decode()
            r = httpx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", headers={"Authorization": f"Bearer {token}"}, json={"raw": raw}, timeout=20)
        elif box.provider == "outlook":
            message = {"subject": subject, "body": {"contentType": "HTML", "content": html_body}, "toRecipients": [{"emailAddress": {"address": a}} for a in to]}
            r = httpx.post("https://graph.microsoft.com/v1.0/me/sendMail", headers={"Authorization": f"Bearer {token}"}, json={"message": message, "saveToSentItems": True}, timeout=20)
        else:
            _, mail = _zoho(box.values.get("data_centre", "com"))
            body = {"fromAddress": box.address, "toAddress": ",".join(to), "subject": subject, "content": html_body, "mailFormat": "html"}
            r = httpx.post(f"{mail}/api/accounts/{box.values['account_id']}/messages", headers={"Authorization": f"Zoho-oauthtoken {token}"}, json=body, timeout=20)
        if r.status_code >= 400:
            raise MailboxError(f"{PROVIDERS[box.provider].name} didn't send it ({r.status_code}). Try again, or connect your mailbox again.")
    except MailboxError as e:
        box.last_error = str(e)[:300]
        raise
    except (OSError, smtplib.SMTPException, httpx.HTTPError) as e:
        box.last_error = f"Couldn't send ({type(e).__name__})."
        raise MailboxError("Couldn't reach your mail server. Try again in a moment.") from None
