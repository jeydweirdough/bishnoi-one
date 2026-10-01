"""A small Discord, in this process, for testing app/discord.py in live mode.

It answers what app/discord.py calls: a webhook (post, edit, delete, which
channel), and the bot (who am I, start a thread, read a channel or thread,
delete a thread). Attachments are kept and served back. `down = True` makes
every call fail as if Discord were unreachable.

    with FakeDiscord() as discord:
        url = discord.webhook_url        # http://127.0.0.1:<port>/api/webhooks/1/token
"""

import itertools
import json
import re
import threading
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

WEBHOOK_ID = "1111"
BOT_ID = "9999"
CHANNEL = "5000"


class FakeDiscord:
    def __init__(self):
        self.ids = itertools.count(10_000)
        self.messages: dict[str, list[dict]] = {CHANNEL: []}  # channel or thread id -> messages, oldest first
        self.files: dict[str, bytes] = {}
        self.down = False
        self.calls = 0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _answer(self, status, body=None):
                data = json.dumps(body).encode() if body is not None else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _body(self):
                size = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(size) if size else b""
                kind = self.headers.get("Content-Type", "")
                if kind.startswith("multipart/"):
                    msg = BytesParser(policy=default).parsebytes(f"Content-Type: {kind}\r\n\r\n".encode() + raw)
                    payload, files = {}, []
                    for part in msg.iter_parts():
                        name = part.get_param("name", header="content-disposition")
                        if name == "payload_json":
                            payload = json.loads(part.get_content())
                        else:
                            files.append((part.get_filename(), part.get_payload(decode=True)))
                    return payload, files
                return (json.loads(raw) if raw else {}), []

            def _route(self, method):
                fake.calls += 1
                if fake.down:
                    self.close_connection = True
                    return self._answer(503, {"message": "down"})
                url = urlparse(self.path)
                query = parse_qs(url.query)
                path = url.path
                if m := re.fullmatch(r"/files/(.+)", path):
                    data = fake.files[m.group(1)]
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    return self.wfile.write(data)
                if m := re.fullmatch(r"/api/v10/webhooks/(\d+)/([^/]+)(?:/messages/(\d+))?", path):
                    return fake.webhook(self, method, m.group(3), query)
                if path == "/api/v10/users/@me":
                    return self._answer(200, {"id": BOT_ID, "username": "bishnoi"})
                if m := re.fullmatch(r"/api/v10/channels/(\d+)/messages/(\d+)/threads", path):
                    return fake.start_thread(self, m.group(2), self._body()[0])
                if m := re.fullmatch(r"/api/v10/channels/(\d+)/messages", path):
                    return fake.read(self, m.group(1), query)
                if m := re.fullmatch(r"/api/v10/channels/(\d+)", path):
                    fake.messages.pop(m.group(1), None)
                    for msg in fake.messages[CHANNEL]:
                        if (msg.get("thread") or {}).get("id") == m.group(1):
                            msg.pop("thread")
                    return self._answer(200, {})
                return self._answer(404, {"message": "Unknown", "code": 0})

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PATCH(self):
                self._route("PATCH")

            def do_DELETE(self):
                self._route("DELETE")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.webhook_url = f"{self.base}/api/webhooks/{WEBHOOK_ID}/secret-token"

    # -- the webhook

    def webhook(self, h, method, message_id, query):
        thread = (query.get("thread_id") or [None])[0]
        where = thread or CHANNEL
        if method == "GET" and not message_id:
            return h._answer(200, {"id": WEBHOOK_ID, "channel_id": CHANNEL})
        if method == "POST":
            payload, files = h._body()
            if where not in self.messages:
                return h._answer(404, {"message": "Unknown Channel", "code": 10003})
            msg = {"id": str(next(self.ids)), "webhook_id": WEBHOOK_ID, "author": {"id": WEBHOOK_ID},
                   "content": payload.get("content", ""), "embeds": payload.get("embeds", []), "attachments": []}
            for name, data in files:
                key = f"{msg['id']}-{name}"
                self.files[key] = data
                msg["attachments"].append({"filename": name, "url": f"{self.base}/files/{key}"})
            self.messages[where].append(msg)
            return h._answer(200, msg)
        found = next((m for m in self.messages.get(where, []) if m["id"] == message_id), None)
        if found is None:
            return h._answer(404, {"message": "Unknown Message", "code": 10008})
        if method == "PATCH":
            payload, _ = h._body()
            found.update({k: v for k, v in payload.items() if k in ("content", "embeds")})
            return h._answer(200, found)
        if method == "DELETE":
            self.messages[where].remove(found)
            return h._answer(204)

    # -- the bot

    def start_thread(self, h, message_id, body):
        starter = next((m for m in self.messages[CHANNEL] if m["id"] == message_id), None)
        if starter is None:
            return h._answer(404, {"message": "Unknown Message", "code": 10008})
        if starter.get("thread"):
            return h._answer(400, {"message": "A thread has already been created for this message", "code": 160004})
        starter["thread"] = {"id": message_id, "name": body["name"]}
        self.messages[message_id] = []
        return h._answer(201, {"id": message_id, "name": body["name"]})

    def read(self, h, channel, query):
        found = list(reversed(self.messages.get(channel, [])))  # newest first, as Discord gives them
        before = (query.get("before") or [None])[0]
        if before:
            found = [m for m in found if int(m["id"]) < int(before)]
        return h._answer(200, found[: int((query.get("limit") or ["50"])[0])])

    # -- for the tests

    def thread_named(self, name):
        starter = next((m for m in self.messages[CHANNEL] if m["embeds"] and m["embeds"][0].get("title") == name), None)
        return self.messages.get(starter["thread"]["id"]) if starter and starter.get("thread") else None

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
