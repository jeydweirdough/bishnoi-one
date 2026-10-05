# Bishnoi One Finance — API

The Finance app's own backend. Its screens are in `../frontend`.

It has **its own sign-in**. Accounts live in this app's own database, and an
account here signs in to this app only.

## Running it

```
cp .env.example .env
uv sync
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
uv run main.py          # http://127.0.0.1:8303  (docs at /docs)
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
| `uv run python -m app.tools.users demo` | Makes this app's demo accounts, password `demo1234` (development only; listed in `app/demo.py`) |
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
| `GET /auth/demo-accounts` | This app's demo accounts that exist, for the sign-in page (development only) |

Send the token as `Authorization: Bearer <token>`. The database keeps only a
hash of each token. Passwords are hashed with scrypt. Five wrong passwords for
one email make it wait 15 minutes (`LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`).

## Settings (`.env`)

| Setting | What it is | Default |
|---|---|---|
| `DATABASE_URL` | This app's own database | `sqlite:///.data/finance.db` |
| `SESSION_HOURS` | How long a sign-in lasts | `10` |
| `ORG_NAME`, `ORG_CURRENCY`, `ORG_LOCALE`, `ORG_TIMEZONE` | The company, as the screens show it | Bishnoi One, PHP, en-PH, Asia/Manila |
| `ALLOWED_HOSTS` | Host names this API answers to | `["localhost", "127.0.0.1"]` |
| `CORS_ORIGINS` | Browser origins allowed to call it directly | none |

## Where things go

| Path | What it's for |
|---|---|
| `app/routers/finance.py` | This app's endpoints, under `/finance` |
| `app/routers/auth.py` | Sign-in and out |
| `app/models.py` | Tables: `users`, `sessions` (add this app's own here) |
| `app/deps.py` | `CurrentUser` / `AdminUser`, for endpoints that need a signed-in person |
| `app/identity.py` | What `/auth/me` tells the screens |
| `app/tools/users.py` | The accounts command |
| `tests/` | Tests (`uv run pytest`) |

Port: screens on 4303, this API on 8303 (screens + 4000).

## Tax

Finance owns tax for every Bishnoi One app (benchmarks/decisions.md, D8): quotes,
pharmacy sales and invoices are all taxed by the rules here.

| Path | What it's for |
|---|---|
| `app/tax/engine.py` | The engine: a sale's lines in, what its invoice shows out. Knows no country |
| `app/tax/packs/ph.py` | The Philippines: VAT, zero-rated, exempt, senior citizen and PWD, percentage tax, the Sales Invoice summary. **Confirm with your accountant before filing** |
| `app/tax/rates.py` | Dated rates in `nbfi_tax_rates`: seeded from the packs on start; a change in the law is a new row from its first day |
| `app/routers/tax.py` | `/tax/setup`, `/tax/profile` (admins), `/tax/rates` (admins), `/tax/compute` |
| `app/routers/integration.py` | `/integration/tax/setup` and `/integration/tax/compute` for the other apps, with `X-Bishnoi-Key` |

Other apps get a key in `INTEGRATION_KEYS` (see `.env.example`). Screens: **Tax** in the sidebar,
with Registration, Rates and Try a sale.
