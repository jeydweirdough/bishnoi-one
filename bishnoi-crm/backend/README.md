# Bishnoi One CRM — API

The CRM app's own backend. Its screens are in `../frontend`.

It has **its own sign-in**. Accounts live in this app's own database, and an
account here signs in to this app only.

## Running it

```
cp .env.example .env
uv sync
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
uv run main.py          # http://127.0.0.1:8302  (docs at /docs)
uv run pytest
```

The database is created, and brought up to date, on every start: migrations
in `migrations/versions` run by themselves (SQLite in `.data/` unless
`DATABASE_URL` says otherwise). Before a migration touches a SQLite file, a copy
is kept beside it (`crm.db.before-<revision>`), and a failed migration puts
it back. To run them by hand: `uv run alembic upgrade head`. A change to the
tables needs a new migration: `uv run alembic revision -m "what changed"`.

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

`--admin` gives the Administrator role; `--role "Team Lead"` and `--team B2C`
pick others (default: Sales Rep, no team). Everything else about people is in
the app, under Administration.

## Administration

Users, Roles & permissions, Teams and the Audit log, under `/admin/...`, each
behind its own permission (`admin.users`, `admin.roles`, `admin.teams`,
`admin.audit`).

- A **role** is a set of permissions (`app/permissions.py`: every area of the
  CRM, including ones not built yet) and a **scope**: whose records it reaches,
  own, team's or all. Each person has one role and may be in one team.
- Four roles to start from: **Administrator** (everything, can't be changed or
  deleted), Manager (all records), Team Lead (team's), Sales Rep (own).
- Nothing may leave the app with nobody able to manage users and roles.
- Every change, sign-in, sign-out and failed sign-in goes to the audit log,
  naming the fields that changed, never their values.
- Endpoints ask for a permission with `Depends(require("customers.edit"))`
  (`app/access.py`).

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

## Customers and activities

| Endpoints | What they are | Permissions |
|---|---|---|
| `/companies` | Companies: list (search, status, owner), add, detail with contacts and activity, change, delete (refused while it has contacts) | `customers.*` |
| `/contacts` | Contacts, each optionally in a company | `customers.*` |
| `/activities` | Calls, emails and notes (logged); meetings and tasks (planned, then done). `state=open/overdue/today/upcoming/done`; `/activities/summary` counts what's still to do | `activities.*` |
| `/people/assignable` | Who a record can be given to | signed in |

Every company, contact and activity has an **owner** and the owner's **team**.
A role's scope decides which of them someone reaches (`app/scope.py`): their
own, their team's, or all. Anything outside that answers 404, and a record can
only be given to someone within it. A time sent without a zone (what a
datetime field gives) is the company's own local time (`ORG_TIMEZONE`).

`uv run python -m app.tools.users demo` also adds sample companies, contacts
and activities, owned by the demo reps, into a database with no companies yet.

## Price rules and tax

How a quote line is priced is set by an admin under **Settings → Price
rules** (`/pricing/...`, `app/conditions.py`, `app/pricing.py`):

1. **The price:** the first of customer-group price, team price and list
   price that has one. The admin sets the order.
2. **Then the adjustments**, in the admin's order: volume scale, promo,
   rep's discount, surcharge. Each can be switched off.
3. **Tax, last**, from Bishnoi One Finance (`app/finance.py`), kept on the quote.

A customer is put in a **price group** on its own page. Rules are dated;
when several match a line, the most specific wins (product and group, then
product, then group, then everything). Promos and bundles are per division:
a team sees only its own. Quotes already made keep their prices.

## Settings (`.env`)

Every setting, with defaults, is in the root README
([section 6](../../README.md#6-settings-env-for-every-app)). The ones only
the CRM has:

| Setting | What it is |
|---|---|
| `INVENTORY_API_URL`, `INVENTORY_API_KEY`, `INVENTORY_APP_URL` | Products and stock from Bishnoi One Inventory. Unset: products are kept here |
| `FINANCE_API_URL`, `FINANCE_API_KEY` | Tax from Bishnoi One Finance. Unset: quotes are priced without tax |
| `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD` | The first administrator, made on start while there are no accounts (Vercel) |

Setting up the links: [MAINTAINING.md](../../MAINTAINING.md), "Linking the
CRM to Inventory" and "Linking the CRM to Finance".

## Deploying on Vercel

Vercel runs the API from `app/server.py` (`[tool.vercel]` in `pyproject.toml`).
It has no lasting disk, so the data lives in Postgres: the database, and the
guarantee letters, which are kept in it (`nbcm_stored_files`).

Every table the CRM makes is named `nbcm_…` (Bishnoi One CRM: `nbcm_users`,
`nbcm_quotes`, and `nbcm_alembic_version` for the migrations), so its tables are easy to tell
apart from any other app's.

1. **Project:** import the repo, with the root directory `bishnoi-crm/backend`.
2. **Database:** any Postgres, as `DATABASE_URL`.
   - **Supabase:** use the **pooler** address (Connect → Transaction pooler,
     port 6543), not `db.<project>.supabase.co`: that direct one is IPv6
     only, which Vercel can't reach. A `#`, `@` or `/` in the password is
     written `%23`, `%40`, `%2F` in the address.
   - **Neon:** the project's **Storage** tab → **Create Database** → Neon →
     connect it to this project. That sets `DATABASE_URL` for you.
3. **Environment variables** (Settings → Environment Variables):

   | Name | Value |
   |---|---|
   | `ENVIRONMENT` | `production` (hides `/docs`) |
   | `ALLOWED_HOSTS` | the API's address, as JSON: `["bishnoi-one-crm-backend.vercel.app"]` |

4. **Redeploy.** The first request builds the tables (migrations run at start,
   one copy at a time).
5. **First account**, from this folder on your computer, with the database's
   address from Vercel (Storage → the database → `.env.local` tab):

   ```
   DATABASE_URL="postgres://…" uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
   ```

   On PowerShell, set it first: `$env:DATABASE_URL="postgres://…"`.

To run the tests on Postgres: `TEST_DATABASE_URL=postgresql://… uv run pytest`.
That database is emptied before every test, so use a throwaway one.

## Where things go

| Path | What it's for |
|---|---|
| `app/routers/crm.py` | This app's endpoints, under `/crm` |
| `app/routers/auth.py` | Sign-in and out |
| `app/models.py` | Tables: `users`, `sessions` (add this app's own here) |
| `app/deps.py` | `CurrentUser` / `AdminUser`, for endpoints that need a signed-in person |
| `app/identity.py` | What `/auth/me` tells the screens |
| `app/tools/users.py` | The accounts command |
| `tests/` | Tests (`uv run pytest`) |

Port: screens on 4302, this API on 8302 (screens + 4000).
