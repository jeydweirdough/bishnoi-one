"""Discord as a store, the way getmeds_discord_system keeps its data there.

The same file is in every Bishnoi One app's backend (app/discord.py); change it in
one, copy it to the rest.

- A **table** is a channel, written through its own webhook.
- A **row** is a starter message whose embed title is the row's id, with a
  thread on it named the same. Each id has exactly one thread.
- The thread holds **one data message**: the row as JSON in a ```json block,
  edited in place on every save. Past 2000 characters it goes as an attached
  `data-<id>.json` instead.
- On start, the bot reads the channel and every thread back, and the rows are
  kept in memory. Reading needs the bot token (a webhook can post, not read).
- A **log** is a thread per app per day (`LOG-CRM-20260926`), one embed per
  line: what was done, to what, by whom, when. Never values.

Switches, as in the Getmeds app:
    DISCORD_ENABLED  true, or nothing is sent (the master off switch)
    DISCORD_MODE     live = really post; mock = nothing leaves this machine
Mock (and off) keep a table in a local JSON file in .data/discord-mock/, so
development works without Discord; a log line is printed instead of posted.

Sending stays within Discord's limits: one webhook call at a time, at most
DISCORD_MAX_PER_MINUTE a minute (Discord allows about 30 per channel), waiting
out X-RateLimit-Reset-After and any 429. Errors never carry a webhook's URL:
it holds the webhook's token.
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

log = logging.getLogger("bishnoi.discord")

CONTENT_LIMIT = 2000  # Discord's limit for a message's text
COLOR = 0x1F3864
DATA_FILE = re.compile(r"^data-.*\.json$")
JSON_BLOCK = re.compile(r"```json\n([\s\S]+?)\n```")
USER_AGENT = "Bishnoi One (https://github.com/jeydweirdough/nabhi, 1)"


class DiscordError(Exception):
    def __init__(self, message: str, status: int | None = None, code: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


def mode_of(enabled: bool, mode: str, webhook_url: str | None) -> str:
    """live, mock or off, as buildTransport decides it."""
    if not enabled:
        return "off"
    if (mode or "mock").lower() != "live":
        return "mock"
    return "live" if webhook_url else "off"


# ---- One Discord API call ------------------------------------------------------------------


def _explain(status: int, what: str) -> str:
    if status == 401 and what in ("channel", "thread"):
        return "Discord refused DISCORD_BOT_TOKEN (401). Copy it again from the bot page"
    if status == 403 and what == "thread":
        return "The bot can't start threads (403). Invite it again with Create Public Threads"
    if status == 403:
        return "The bot can't see the channel (403). Add it to the server with View Channels and Read Message History"
    if status == 404 and what == "message":
        return "Discord no longer has that message (404). It may have been deleted"
    if status == 404 and what == "webhook":
        return "Discord doesn't know this webhook (404). Check the webhook URL"
    if status == 404:
        return "Discord no longer has that message or thread (404). It may have been deleted"
    return f"Discord answered {status} while reading {'the channel' if what == 'channel' else f'a {what}'}"


def _what(url: str) -> str:
    if "/threads" in url:
        return "thread"
    if "/channels/" in url:
        return "channel"
    if "/messages/" in url:
        return "message"
    return "webhook"


def _multipart(payload: dict, files: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n'.encode()
        + json.dumps(payload).encode()
        + b"\r\n"
    )
    for i, (name, kind, data) in enumerate(files):
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="files[{i}]"; filename="{name}"\r\nContent-Type: {kind}\r\n\r\n'
        parts.append(head.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def request(method: str, url: str, *, bot: str | None = None, body: Any = None,
            files: list[tuple[str, str, bytes]] | None = None, timeout: float = 10) -> Any:
    """One call, with Discord's rate limits waited out (up to 5 tries on a 429)."""
    for attempt in range(1, 6):
        headers = {"User-Agent": USER_AGENT}
        if bot:
            headers["Authorization"] = f"Bot {bot}"
        data = None
        if files:
            data, headers["Content-Type"] = _multipart(body or {}, files)
        elif body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60 if files else timeout) as res:
                text = res.read()
                if res.headers.get("X-RateLimit-Remaining") == "0":
                    time.sleep(min(float(res.headers.get("X-RateLimit-Reset-After") or 0), 60))
                return json.loads(text) if text else None
        except urllib.error.HTTPError as e:
            info = {}
            try:
                info = json.loads(e.read() or b"{}")
            except ValueError:
                pass
            if e.code == 429 and attempt < 5:
                time.sleep(min(float(e.headers.get("Retry-After") or info.get("retry_after") or 1), 60))
                continue
            raise DiscordError(_explain(e.code, _what(url)), e.code, info.get("code")) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise DiscordError(f"Couldn't reach Discord ({type(e).__name__})") from None
    raise DiscordError("Discord kept asking to wait (429)", 429)


# ---- A webhook, and the bot beside it --------------------------------------------------------


class Webhook:
    """LiveDiscord: posts through one webhook at Discord's pace; reads back with the bot."""

    def __init__(self, url: str, bot_token: str | None = None, per_minute: int = 30):
        match = re.search(r"/webhooks/(\d+)/([^/?]+)", url or "")
        if not match:
            raise DiscordError("That doesn't look like a Discord webhook URL")
        base = url.split("/api/")[0] if "/api/" in url else "https://discord.com"
        self.api = f"{base}/api/v10"
        self.id, self.token = match.group(1), match.group(2)
        self.bot = bot_token or None
        self.per_minute = max(1, per_minute)
        self._sent: deque[float] = deque()
        self._lock = threading.Lock()
        self._channel: str | None = None
        self._me: dict | None = None

    @property
    def hook(self) -> str:
        return f"{self.api}/webhooks/{self.id}/{self.token}"

    def _pace(self) -> None:
        """At most per_minute webhook calls in any minute (the headers don't warn about this one)."""
        while True:
            now = time.monotonic()
            while self._sent and now - self._sent[0] > 60:
                self._sent.popleft()
            if len(self._sent) < self.per_minute:
                self._sent.append(now)
                return
            time.sleep(60 - (now - self._sent[0]) + 0.05)

    def _call(self, method: str, url: str, **kw) -> Any:
        with self._lock:  # one at a time: parallel calls only race for the same bucket
            self._pace()
            return request(method, url, **kw)

    def post(self, payload: dict, *, thread_id: str | None = None, files: list[tuple[str, str, bytes]] | None = None) -> dict:
        query = "?wait=true" + (f"&thread_id={thread_id}" if thread_id else "")
        return self._call("POST", f"{self.hook}{query}", body=payload, files=files) or {}

    def edit(self, message_id: str, payload: dict, *, thread_id: str | None = None) -> dict:
        query = f"?thread_id={thread_id}" if thread_id else ""
        return self._call("PATCH", f"{self.hook}/messages/{message_id}{query}", body=payload) or {}

    def delete_message(self, message_id: str, *, thread_id: str | None = None) -> None:
        query = f"?thread_id={thread_id}" if thread_id else ""
        try:
            self._call("DELETE", f"{self.hook}/messages/{message_id}{query}")
        except DiscordError as e:
            if e.status != 404:
                raise

    def channel(self) -> str:
        if not self._channel:
            self._channel = request("GET", self.hook)["channel_id"]
        return self._channel

    def me(self) -> dict:
        if self._me is None:
            self._me = request("GET", f"{self.api}/users/@me", bot=self.bot)
        return self._me

    def start_thread(self, message_id: str, name: str) -> str:
        """A thread started on one of our messages has the message's id. Needs Create Public Threads."""
        try:
            thread = request("POST", f"{self.api}/channels/{self.channel()}/messages/{message_id}/threads", bot=self.bot,
                             body={"name": name[:100], "auto_archive_duration": 10080})
            return thread["id"]
        except DiscordError as e:
            if e.code == 160004:  # already has a thread, e.g. on a retry
                return message_id
            raise

    def delete_thread(self, thread_id: str) -> None:
        try:
            request("DELETE", f"{self.api}/channels/{thread_id}", bot=self.bot)
        except DiscordError as e:
            if e.status != 404:
                raise

    def thread_messages(self, thread_id: str) -> list[dict]:
        """Every message in a thread, oldest first."""
        found: list[dict] = []
        before = None
        while True:
            page = request("GET", f"{self.api}/channels/{thread_id}/messages?limit=100" + (f"&before={before}" if before else ""), bot=self.bot)
            found.extend(page)
            if len(page) < 100:
                return list(reversed(found))
            before = page[-1]["id"]

    def history(self) -> list[dict]:
        """Every message this webhook posted in its channel, newest first. Needs the bot."""
        found: list[dict] = []
        before = None
        while True:
            page = request("GET", f"{self.api}/channels/{self.channel()}/messages?limit=100" + (f"&before={before}" if before else ""), bot=self.bot)
            found.extend(m for m in page if m.get("webhook_id") == self.id)
            if len(page) < 100:
                break
            before = page[-1]["id"]
        if found and all(not m.get("content") and not m.get("embeds") for m in found):
            raise DiscordError("Discord sent the messages back empty. Turn on Message Content Intent on the bot page in the Developer Portal")
        return found


# ---- A table: a row per thread -----------------------------------------------------------------


@dataclass
class Row:
    data: dict | None = None
    thread_id: str | None = None
    starter_id: str | None = None
    message_id: str | None = None


def _to_message(data: dict, row_id: str) -> tuple[str, tuple[str, str, bytes] | None]:
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    for text in (pretty, json.dumps(data, ensure_ascii=False, separators=(",", ":"))):
        content = f"```json\n{text}\n```"
        if len(content) <= CONTENT_LIMIT:
            return content, None
    safe = re.sub(r"[^a-zA-Z0-9_-]", "-", row_id).lower()
    return (f'Data for row "{row_id}" is attached as a JSON file (over {CONTENT_LIMIT} characters).',
            (f"data-{safe}.json", "application/json", pretty.encode()))


def _json_in(content: str | None) -> dict | None:
    match = JSON_BLOCK.search(content or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


class Table:
    """createDiscordTable: rows kept in memory, stored in Discord (or a local file in mock)."""

    def __init__(self, name: str, *, webhook_url: str | None, bot_token: str | None, enabled: bool, mode: str,
                 per_minute: int = 30, mock_dir: Path | None = None, describe=None):
        self.name = name
        self.mode = mode_of(enabled, mode, webhook_url)
        self.live = Webhook(webhook_url, bot_token, per_minute) if self.mode == "live" else None
        if self.live and not bot_token:
            raise DiscordError(f"The {name} table needs DISCORD_BOT_TOKEN to read its rows back")
        self.file = (mock_dir or Path(".data/discord-mock")) / f"{name}.json"
        self.rows: dict[str, Row] = {}
        self.describe = describe or (lambda data: "")
        self._lock = threading.RLock()
        self.loaded_at = 0.0
        self.ready = False  # read from Discord (or the file) at least once

    # -- reading

    def load(self) -> None:
        with self._lock:
            if self.mode != "live":
                self.rows = {k: Row(data=v) for k, v in self._read_file().items()}
            else:
                self.rows = self._read_discord()
            self.loaded_at = time.monotonic()
            self.ready = True

    def fresh(self, max_age: float = 60) -> None:
        """Reads Discord again when the copy here is older than max_age: another server may have saved since."""
        if self.mode == "live" and time.monotonic() - self.loaded_at > max_age:
            try:
                self.load()
            except DiscordError as e:
                self.loaded_at = time.monotonic()  # try again in a minute, not on every request
                log.warning("[discord:%s] kept the copy in memory: %s", self.name, e)

    def _read_file(self) -> dict:
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}

    def _read_discord(self) -> dict[str, Row]:
        live = self.live
        bot = live.me()
        rows: dict[str, Row] = {}
        for m in reversed(live.history()):  # oldest first: the first starter for an id wins
            row_id = (m.get("embeds") or [{}])[0].get("title")
            if not row_id:
                continue
            row = rows.setdefault(row_id, Row(starter_id=m["id"]))
            if not row.thread_id and m.get("thread"):
                row.thread_id = m["thread"]["id"]
        for row_id, row in rows.items():
            if not row.thread_id:
                continue
            for tm in reversed(live.thread_messages(row.thread_id)):  # newest data message wins
                if tm.get("webhook_id") != live.id and (tm.get("author") or {}).get("id") != bot.get("id"):
                    continue
                data = _json_in(tm.get("content"))
                if data is None:
                    file = next((a for a in tm.get("attachments") or [] if DATA_FILE.match(a.get("filename", ""))), None)
                    if file:
                        try:
                            with urllib.request.urlopen(urllib.request.Request(file["url"], headers={"User-Agent": USER_AGENT}), timeout=15) as res:
                                data = json.loads(res.read())
                        except (OSError, ValueError):
                            data = None
                if data is not None:
                    row.data, row.message_id = data, tm["id"]
                    break
        log.info("[discord:%s] loaded %d row(s) from Discord", self.name, sum(1 for r in rows.values() if r.data is not None))
        return rows

    def get(self, row_id: str) -> dict | None:
        row = self.rows.get(row_id)
        return row.data if row else None

    def all(self) -> list[dict]:
        return [r.data for r in self.rows.values() if r.data is not None]

    # -- writing: raises DiscordError when Discord doesn't take it, and changes nothing here then

    def save(self, row_id: str, data: dict) -> None:
        with self._lock:
            if self.mode != "live":
                self.rows.setdefault(row_id, Row()).data = data
                self._write_file()
                return
            if not self.ready:
                raise DiscordError(f"the {self.name} haven't been read from Discord yet")
            row = self.rows.get(row_id) or Row()
            self._ensure_thread(row_id, row, data)
            content, file = _to_message(data, row_id)
            payload: dict = {"allowed_mentions": {"parse": []}, "content": content}
            if file:
                payload["attachments"] = [{"id": 0, "filename": file[0]}]
            if row.message_id and not file:
                try:
                    self.live.edit(row.message_id, payload, thread_id=row.thread_id)
                    row.data = data
                    self.rows[row_id] = row
                    return
                except DiscordError as e:
                    log.warning("[discord:%s] editing %s in place failed (%s), replacing it", self.name, row_id, e)
            old = row.message_id
            posted = self.live.post(payload, thread_id=row.thread_id, files=[file] if file else None)
            row.message_id, row.data = posted.get("id"), data
            self.rows[row_id] = row
            if old and old != row.message_id:  # one data message per row
                try:
                    self.live.delete_message(old, thread_id=row.thread_id)
                except DiscordError:
                    pass

    def _ensure_thread(self, row_id: str, row: Row, data: dict) -> None:
        if row.thread_id:
            return
        if not row.starter_id:
            posted = self.live.post({"allowed_mentions": {"parse": []}, "embeds": [{
                "title": row_id[:256],
                "description": f"Table: **{self.name}** · Row: **{row_id}**\n{self.describe(data)}"[:4096],
                "color": COLOR,
            }]})
            row.starter_id = posted["id"]
        row.thread_id = self.live.start_thread(row.starter_id, row_id)

    def delete(self, row_id: str) -> None:
        with self._lock:
            row = self.rows.pop(row_id, None)
            if self.mode != "live":
                self._write_file()
                return
            if row and row.thread_id:
                self.live.delete_thread(row.thread_id)
            if row and row.starter_id:
                self.live.delete_message(row.starter_id)

    def _write_file(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: r.data for k, r in self.rows.items() if r.data is not None}, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file)


def day_ids(prefix: str, rows: list[str], timezone: str, now: datetime | None = None) -> str:
    """The next id in the Getmeds format, numbered from 0001 each day in the company's time zone:
    ANN-20260926-0001."""
    today = (now or datetime.now(UTC)).astimezone(ZoneInfo(timezone)).strftime("%Y%m%d")
    stem = f"{prefix}-{today}-"
    taken = [int(r[len(stem):]) for r in rows if r.startswith(stem) and r[len(stem):].isdigit()]
    return f"{stem}{max(taken, default=0) + 1:04d}"


# ---- Logs: a thread per app per day, posted from a background queue -----------------------------


@dataclass
class Line:
    action: str
    actor: str
    target: str = ""
    target_type: str | None = None
    target_id: str | None = None
    fields: list[str] = field(default_factory=list)
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


class Logs:
    """The app's log lines, posted to Discord without holding up the request that made them.

    Lines wait in a queue (at most 1000; past that, new ones are dropped with a
    warning) and a background worker posts them at Discord's pace, each tried
    up to 5 times. A webhook Discord refuses outright stops the worker.
    """

    def __init__(self, app_code: str, *, webhook_url: str | None, bot_token: str | None, enabled: bool, mode: str,
                 timezone: str, per_minute: int = 30):
        self.code = app_code.upper()
        self.mode = mode_of(enabled, mode, webhook_url)
        self.timezone = timezone
        self.live = Webhook(webhook_url, bot_token, per_minute) if self.mode == "live" else None
        self.threads: dict[str, str] = {}  # day id -> thread id
        self.queue: queue.Queue[Line] = queue.Queue(maxsize=1000)
        self.stopped: str | None = None
        self._worker: threading.Thread | None = None

    def send(self, line: Line) -> None:
        if self.mode == "off":
            return
        if self.mode == "mock":
            log.info("[discord:mock] %s log: %s · %s%s", self.code, line.action, line.actor, f" · {line.target}" if line.target else "")
            return
        if self.stopped:
            return
        try:
            self.queue.put_nowait(line)
        except queue.Full:
            log.warning("[discord] %s log queue is full: a line was dropped", self.code)
            return
        if not self._worker or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._run, name=f"discord-log-{self.code}", daemon=True)
            self._worker.start()

    def flush(self, timeout: float = 30) -> None:
        """Waits for the queue to empty (tests, shutdown)."""
        end = time.monotonic() + timeout
        while self.queue.unfinished_tasks and time.monotonic() < end:
            time.sleep(0.05)

    def _run(self) -> None:
        while True:
            try:
                line = self.queue.get(timeout=30)
            except queue.Empty:
                return  # idle: a new line starts another worker
            try:
                for attempt in range(1, 6):
                    try:
                        self._post(line)
                        break
                    except DiscordError as e:
                        if e.status in (401, 403, 404) and "webhook" in str(e).lower():
                            self.stopped = str(e)
                            log.error("[discord] %s logs stopped: %s", self.code, e)
                            return
                        if attempt == 5:
                            log.warning("[discord] %s log line not sent after 5 tries: %s", self.code, e)
                        else:
                            time.sleep(min(2 ** attempt, 30))
            finally:
                self.queue.task_done()

    def day_thread(self, at: datetime) -> str | None:
        day = f"LOG-{self.code}-{at.astimezone(ZoneInfo(self.timezone)).strftime('%Y%m%d')}"
        if day in self.threads:
            return self.threads[day]
        if not self.live.bot:
            return None  # without the bot there are no threads: lines go in the channel
        for m in self.live.history():
            if (m.get("embeds") or [{}])[0].get("title") == day:
                if m.get("thread"):
                    self.threads[day] = m["thread"]["id"]
                    return self.threads[day]
                self.threads[day] = self.live.start_thread(m["id"], day)
                return self.threads[day]
        starter = self.live.post({"allowed_mentions": {"parse": []}, "embeds": [{
            "title": day, "color": COLOR,
            "description": f"Log of **Bishnoi One {self.code.title()}** for {at.astimezone(ZoneInfo(self.timezone)).strftime('%A, %d %B %Y')}.",
        }]})
        self.threads[day] = self.live.start_thread(starter["id"], day)
        return self.threads[day]

    def _post(self, line: Line) -> None:
        fields = []
        if line.target:
            fields.append({"name": "What", "value": f"{line.target_type + ': ' if line.target_type else ''}{line.target}"[:1024], "inline": False})
        if line.fields:
            fields.append({"name": "Changed", "value": ", ".join(line.fields)[:1024], "inline": False})
        if line.target_id:
            fields.append({"name": "Id", "value": str(line.target_id)[:1024], "inline": True})
        embed = {
            "title": line.action[:256],
            "color": COLOR,
            "fields": fields,
            "footer": {"text": line.actor[:200]},
            "timestamp": line.at.astimezone(UTC).isoformat(),
        }
        self.live.post({"allowed_mentions": {"parse": []}, "embeds": [embed]}, thread_id=self.day_thread(line.at))


def logs_for(code: str, settings) -> Logs:
    """This app's log, from its settings (DISCORD_* in .env)."""
    return Logs(code, webhook_url=settings.secret(settings.discord_logs_webhook_url), bot_token=settings.secret(settings.discord_bot_token),
                enabled=settings.discord_enabled, mode=settings.discord_mode, timezone=settings.org_timezone,
                per_minute=settings.discord_max_per_minute)


# ---- Hooks: what each app sends to its log ------------------------------------------------------


def mirror_audit(sessions, model, logs: Logs) -> None:
    """Sends every audit line (model: the app's audit table) to the log once its change is committed,
    and never one whose change was rolled back."""
    from sqlalchemy import event

    def after_flush(session, _context) -> None:
        for obj in session.new:
            if isinstance(obj, model):
                session.info.setdefault("discord_lines", []).append(Line(
                    action=obj.action, actor=obj.actor or "", target=obj.target or "", target_type=obj.target_type,
                    target_id=obj.target_id, fields=list(obj.fields or []),
                ))

    def after_commit(session) -> None:
        for line in session.info.pop("discord_lines", []):
            logs.send(line)

    def after_rollback(session) -> None:
        session.info.pop("discord_lines", None)

    event.listen(sessions, "after_flush", after_flush)
    event.listen(sessions, "after_commit", after_commit)
    event.listen(sessions, "after_rollback", after_rollback)


VERBS = {"POST": "added", "PUT": "changed", "PATCH": "changed", "DELETE": "deleted"}


def log_requests(app, logs: Logs) -> None:
    """For an app without an audit table: every change that went through, and every sign-in, as a line.
    Who did it comes from request.state.actor, which the sign-in dependency sets."""

    @app.middleware("http")
    async def _log(request, call_next):
        response = await call_next(request)
        verb = VERBS.get(request.method)
        if (verb and response.status_code < 400) or request.url.path == "/auth/login":
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            if request.url.path == "/auth/login":
                action, who = ("auth.signed_in" if response.status_code < 400 else "auth.sign_in_failed"), "someone signing in"
            else:
                action, who = f"{path} {verb}", getattr(request.state, "actor", "")
            logs.send(Line(action=action, actor=who, target_id=", ".join(str(v) for v in request.path_params.values()) or None))
        return response
