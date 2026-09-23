# Orbit Executive Admin — API

The Executive Admin app's own backend. Its screens are in `../frontend`.

It has **its own sign-in**. Accounts live in this app's own database, and an
account here signs in to this app only.

## Running it

```
cp .env.example .env
uv sync
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
uv run main.py          # http://127.0.0.1:8300  (docs at /docs)
uv run pytest
```

The database and its tables are created on first start (SQLite in `.data/`
unless `DATABASE_URL` says otherwise).

## Accounts

There is no sign-up page. Accounts are made from the command line:

| Command | Does |
|---|---|
| `uv run python -m app.tools.users add --email … --name "…" [--admin]` | Makes an account; asks for its password |
| `uv run python -m app.tools.users list` | Lists accounts |
| `uv run python -m app.tools.users password --email …` | Sets a new password; ends that person's sessions |
| `uv run python -m app.tools.users disable --email …` | Switches the account off; ends its sessions |
| `uv run python -m app.tools.users enable --email …` | Switches it back on |

`--admin` accounts can run this app's settings; the rest just use it.

## Sign-in endpoints

| Endpoint | What it does |
|---|---|
| `POST /auth/login` | `{email, password}` → `{accessToken, expiresIn}` |
| `GET /auth/me` | Who is signed in, and what this app lets them do |
| `POST /auth/logout` | Ends the session |

Send the token as `Authorization: Bearer <token>`. The database keeps only a
hash of each token. Passwords are hashed with scrypt. Five wrong passwords for
one email make it wait 15 minutes (`LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`).

## Settings (`.env`)

| Setting | What it is | Default |
|---|---|---|
| `DATABASE_URL` | This app's own database | `sqlite:///.data/admin.db` |
| `SESSION_HOURS` | How long a sign-in lasts | `10` |
| `ORG_NAME`, `ORG_CURRENCY`, `ORG_LOCALE`, `ORG_TIMEZONE` | The company, as the screens show it | Orbit, PHP, en-PH, Asia/Manila |
| `ALLOWED_HOSTS` | Host names this API answers to | `["localhost", "127.0.0.1"]` |
| `CORS_ORIGINS` | Browser origins allowed to call it directly | none |

## Where things go

| Path | What it's for |
|---|---|
| `app/routers/admin.py` | This app's endpoints, under `/admin` |
| `app/routers/auth.py` | Sign-in and out |
| `app/models.py` | Tables: `users`, `sessions` (add this app's own here) |
| `app/deps.py` | `CurrentUser` / `AdminUser`, for endpoints that need a signed-in person |
| `app/identity.py` | What `/auth/me` tells the screens |
| `app/tools/users.py` | The accounts command |
| `tests/` | Tests (`uv run pytest`) |

Port: screens on 4300, this API on 8300 (screens + 4000).
