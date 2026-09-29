"""Starts one Nabhi API (CRM or Inventory) inside Nabhi.exe.

Nabhi.exe starts this as a child process, on the PC's own address only
(127.0.0.1), and hands it its settings as environment variables in memory:
DATABASE_URL (from the company's decrypted connection file), NABHI_PORT, and
the keys the apps use to talk to each other. Nothing is read from or written
to a .env file.

When it's ready it prints one line, `NABHI_READY <port>`, which Nabhi.exe waits
for before it opens the screens. If the database refuses (wrong password, or a
database newer than this copy of Nabhi), the API still starts and answers every
request with what's wrong (app/server.py), so the screen can say it plainly.
"""

import os
import sys


def main() -> None:
    port = int(os.environ.get("NABHI_PORT", "0"))
    if not port:
        sys.exit("NABHI_PORT is required.")
    # The app's settings class reads these; the host list is this PC only.
    os.environ.setdefault("ALLOWED_HOSTS", '["127.0.0.1", "localhost"]')

    import uvicorn

    from app.server import app  # builds the API (and brings the database up to date) now

    class Ready(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets)
            print(f"NABHI_READY {port}", flush=True)

    Ready(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)).run()


if __name__ == "__main__":
    main()
