# Bishnoi One Executive Admin — API

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
| `uv run python -m app.tools.users add --email … --name "…" [--role "…" \| --admin]` | Makes an account (Executive Assistant unless told otherwise); asks for its password |
| `uv run python -m app.tools.users list` | Lists accounts |
| `uv run python -m app.tools.users roles` | Lists roles and how many people have each |
| `uv run python -m app.tools.users role --email … --role "…"` | Changes someone's role (never the last administrator's) |
| `uv run python -m app.tools.users demo` | Makes this app's demo accounts, one per role, password `demo1234`, and seeds sample records (development only; listed in `app/demo.py`) |
| `uv run python -m app.tools.users password --email …` | Sets a new password; ends that person's sessions |
| `uv run python -m app.tools.users disable --email …` | Switches the account off; ends its sessions |
| `uv run python -m app.tools.users enable --email …` | Switches it back on |

The roles start as Administrator (everything, can't be changed), Executive
Assistant, Compliance Officer, Auditor (read-only) and Marketing Assistant
(promotional materials only). What each may do is in
`app/permissions.py`; administrators can change that from the app. `--admin`
is short for `--role Administrator`.

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

## Promotional materials

`app/routers/materials.py`. The marketing assistant adds a material (type,
product, quantity needed, size and specifications, date needed, budget) and
uploads its design (PDF or picture, up to 3 MB, kept in the database); **Submit for
review** sends it to Pharmacy, where the pharmacist approves it, returns it with
comments (a new version is uploaded and submitted again) or rejects it. The
Executive Assistant (`materials.produce`) orders production and marks it
received into stock, with a photo of the delivery as proof. **Request distribution** asks the CRM: the team's manager
approves or rejects it there, and Admin records it as distributed, with a photo of the hand-over or the
signed receipt as proof. Admin asks
Pharmacy and the CRM for their answer when someone opens the material
(`app/linked.py`). Both links are made on the Platform's Connections page
(Admin → Pharmacy, Admin → CRM); without them the screens say Admin isn't
connected yet.

## Settings (`.env`)

| Setting | What it is | Default |
|---|---|---|
| `DATABASE_URL` | This app's own database | `sqlite:///.data/admin.db` |
| `SESSION_HOURS` | How long a sign-in lasts | `10` |
| `ORG_NAME`, `ORG_CURRENCY`, `ORG_LOCALE`, `ORG_TIMEZONE` | The company, as the screens show it | Bishnoi One, PHP, en-PH, Asia/Manila |
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
