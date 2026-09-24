# Nabhi Platform — API

The Platform app's own backend: the control tower above every Nabhi
application. Its screens are in `../frontend`.

It doesn't run the pharmacy, the CRM or the inventory. It keeps the record of
the platform itself — companies, the people at them and which applications
each may use, the applications and whether they're working — and what is going
wrong: complaints, bugs, incidents.

## Running it

```
cp .env.example .env
uv sync
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
uv run main.py          # http://127.0.0.1:8305  (docs at /docs)
uv run pytest
```

The database is brought up to date on every start (Alembic, `migrations/`):
SQLite in `.data/` unless `DATABASE_URL` says otherwise. Every table is
`nbpl_…`, and the revision is kept in `nbpl_alembic_version`. A database from
before migrations (plain `users` / `sessions`) is renamed and kept; a SQLite
file is copied beside itself (`platform.db.before-<revision>`) before any
migration touches it.

For development, `uv run python -m app.tools.users demo` makes the demo
accounts and, on an empty platform, sample companies, people, tickets and an
incident.

## Two kinds of people

| | Who | Table |
|---|---|---|
| **Staff** | Sign in to this console. *Platform Admin* (`--admin`) changes anything; *Support* sees everything and works tickets and incidents. | `nbpl_users` |
| **Platform users** | The people at the companies: one account each, with the applications they may use and their role in each. They don't sign in here; each application still has its own sign-in. | `nbpl_identities`, `nbpl_identity_apps` |

Three levels of administration: Platform Admin (here), company admin (a user
with `isCompanyAdmin`) and application admin (a grant with `isAppAdmin`).
Access never goes past the company's: a person can only be given an
application their company has, and loses it when the company does.

## Staff accounts

| Command | Does |
|---|---|
| `uv run python -m app.tools.users add --email … --name "…" [--admin]` | Makes an account; asks for its password |
| `uv run python -m app.tools.users list` | Lists accounts |
| `uv run python -m app.tools.users demo` | Demo accounts (password `demo1234`) and sample records (development only) |
| `uv run python -m app.tools.users password --email …` | Sets a new password; ends that person's sessions |
| `uv run python -m app.tools.users disable --email …` | Switches the account off; ends its sessions |
| `uv run python -m app.tools.users enable --email …` | Switches it back on |

On a host you can't run the tool against (Vercel), set `FIRST_ADMIN_EMAIL`,
`FIRST_ADMIN_NAME` and `FIRST_ADMIN_PASSWORD`: they make the first Platform
Admin into an empty database and are ignored after.

## Endpoints

Send the token as `Authorization: Bearer <token>`. Query parameters are
snake_case (`?company_id=…`); bodies and answers are camelCase.

| Area | Endpoints |
|---|---|
| Sign-in | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/password`, `GET /auth/demo-accounts` |
| Dashboard | `GET /platform/dashboard`, `GET /platform/banner`, `GET /platform/options` |
| Organizations | `GET/POST /platform/companies`, `GET/PATCH /platform/companies/{id}`, `PUT …/{id}/applications`, `POST …/{id}/units`, `PATCH/DELETE …/{id}/units/{unit}` |
| Applications | `GET/POST /platform/applications`, `GET/PATCH …/{id}`, `POST …/{id}/deployments`, `POST …/{id}/integrations`, `GET /platform/deployments`, `GET /platform/integrations`, `PATCH/DELETE /platform/integrations/{id}` |
| Users | `GET/POST /platform/users`, `GET/PATCH …/{id}`, `PUT/DELETE …/{id}/applications/{app}` |
| Access | `GET/POST /platform/access/requests`, `POST …/{id}/decision`, `GET /platform/access/organizations`, `…/applications`, `…/roles`, `GET /platform/staff`, `PATCH /platform/staff/{id}`, `GET /platform/sessions`, `DELETE /platform/sessions/{id}` |
| Support | `GET/POST /platform/tickets`, `GET/PATCH …/{id}`, `POST …/{id}/notes` |
| Incidents | `GET/POST /platform/incidents`, `GET/PATCH …/{id}`, `POST …/{id}/updates` |
| Monitoring | `GET /platform/monitoring[?refresh=true]`, `GET /platform/monitoring/history`, `GET /platform/traffic` |
| Activity & audit | `GET /platform/activity` |
| Communications | `GET/POST /platform/announcements`, `PATCH/DELETE …/{id}` |
| Settings | `GET /platform/settings`, `PUT /platform/settings/{platform,monitoring,notifications,security}` |
| For the other apps | `GET /public/notices?app=crm&company=getmeds` (no sign-in) |

## How monitoring works

Each application is registered with a health address (its API's `/health`).
The platform asks every one at once when somebody looks and the last answer is
older than Settings › Monitoring says — not on a timer, because a serverless
host runs nothing between requests. 2xx is operational (degraded if slow); a
503 from an app that couldn't start names the setting to check; anything else
is down. A Platform Admin can declare maintenance, degraded or an outage over
what the check says.

Traffic is the Platform API's own requests, counted per minute. The other
applications' traffic stays with them; what the platform sees of them is how
fast each answers its health check.

## Settings (`.env`)

| Setting | What it is | Default |
|---|---|---|
| `DATABASE_URL` | This app's own database | `sqlite:///.data/platform.db` |
| `FIRST_ADMIN_EMAIL`, `_NAME`, `_PASSWORD` | The first Platform Admin, into an empty database | none |
| `SESSION_HOURS`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES` | Sign-in rules to start with; Settings › Security wins once saved | 10, 5, 15 |
| `ORG_NAME`, `ORG_CURRENCY`, `ORG_LOCALE`, `ORG_TIMEZONE` | The platform, as the screens show it | Nabhi, PHP, en-PH, Asia/Manila |
| `ALLOWED_HOSTS` | Host names this API answers to | `["localhost", "127.0.0.1"]` |
| `CORS_ORIGINS` | Browser origins allowed to call it directly | none |

On Vercel the API runs from `app.server:app` (`pyproject.toml`); if it can't
start, every request gets a 503 naming the setting to look at.

## Where things go

| Path | What it's for |
|---|---|
| `app/models.py` | Every table (`nbpl_…`) |
| `migrations/versions/` | How the database gets there |
| `app/routers/` | One file per area of the console |
| `app/monitor.py`, `app/traffic.py` | Health checks; the API's own traffic |
| `app/platform_settings.py` | The settings changed from the screens |
| `app/audit.py` | The audit log, and its four categories |
| `app/deps.py` | `CurrentUser` (any staff) / `AdminUser` (Platform Admin) |
| `tests/` | Tests (`uv run pytest`) |

Port: screens on 4305, this API on 8305 (screens + 4000).
