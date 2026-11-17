# Bishnoi One Finance — API

The Finance app's own backend. It is a module of the one backend (`backend/main.py`), under `/finance`; its screens are in the one app
(`bishnoi-one-app/frontend`, at `/finance`).

It has **its own sign-in**. Accounts live in this app's own database, and an
account here signs in to this app only.

## Running it

```
cd backend               # the one backend; settings in backend/.env (see backend/.env.example)
uv sync
uv run python -m modules.finance.tools.users add --email you@example.com --name "Your Name" --admin
uv run main.py            # every module; this one at http://127.0.0.1:8300/finance  (docs at /finance/docs)
uv run pytest modules/finance/tests
```

The database and its tables are created on first start (SQLite in `.data/`
unless `DATABASE_URL` says otherwise).

## Accounts

There is no sign-up page. Accounts are made from the command line:

| Command | Does |
|---|---|
| `uv run python -m modules.finance.tools.users add --email … --name "…" [--admin]` | Makes an account; asks for its password |
| `uv run python -m modules.finance.tools.users list` | Lists accounts |
| `uv run python -m modules.finance.tools.users demo` | Makes this app's demo accounts, password `demo1234` (development only; listed in `demo.py`) |
| `uv run python -m modules.finance.tools.users password --email …` | Sets a new password; ends that person's sessions |
| `uv run python -m modules.finance.tools.users disable --email …` | Switches the account off; ends its sessions |
| `uv run python -m modules.finance.tools.users enable --email …` | Switches it back on |

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
| `routers/finance.py` | This app's endpoints, under `/finance` |
| `routers/auth.py` | Sign-in and out |
| `models.py` | Tables: `users`, `sessions` (add this app's own here) |
| `deps.py` | `CurrentUser` / `AdminUser`, for endpoints that need a signed-in person |
| `identity.py` | What `/auth/me` tells the screens |
| `tools/users.py` | The accounts command |
| `tests/` | Tests (`uv run pytest modules/finance/tests`) |

Port: none of its own: it answers under its path in the one backend (port 8300), and its screens are in the one app (port 4301).

## Tax

Finance owns tax for every Bishnoi One app (benchmarks/decisions.md, D8): quotes,
pharmacy sales and invoices are all taxed by the rules here.

| Path | What it's for |
|---|---|
| `tax/engine.py` | The engine: a sale's lines in, what its invoice shows out. Knows no country |
| `tax/packs/ph.py` | The Philippines: VAT, zero-rated, exempt, senior citizen and PWD, percentage tax, the Sales Invoice summary. **Confirm with your accountant before filing** |
| `tax/rates.py` | Dated rates in `nbfi_tax_rates`: seeded from the packs on start; a change in the law is a new row from its first day |
| `routers/tax.py` | `/tax/setup`, `/tax/profile` (admins), `/tax/rates` (admins), `/tax/compute` |
| `routers/integration.py` | `/integration/tax/setup` and `/integration/tax/compute` for the other apps, with `X-Bishnoi-Key` |

Other apps get a key in `INTEGRATION_KEYS` (see `.env.example`). Screens: **Tax** in the sidebar,
with Registration, Rates and Try a sale.
