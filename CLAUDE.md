# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Bishnoi One: business apps (pharma distribution first; Philippines first) kept in one repo. Each `bishnoi-<app>/` folder is one module's API, `backend/` (Python 3.13, FastAPI, SQLAlchemy, Alembic, run with `uv`), with its own database and settings; APIs do not import from each other. **Every module's screens are in one Next.js app, `bishnoi-one-app/frontend`** (Next.js 16 App Router, React 19, Ant Design 6, Tailwind 4; port 4301, one.bishnoi.ai at cutover), each module under its path. The per-app frontends were removed on 2026-10-24.

| Module | Path in the one app | API | Table prefix |
|---|---|---|---|
| admin (Executive Admin) | `/admin` | 8300 | `nbad_` |
| crm | `/crm` | 8302 | `nbcm_` |
| finance | `/finance` | 8303 | `nbfi_` |
| inventory | `/inventory` | 8304 | `nbin_` |
| platform | `/platform` (Admin Console: APIs, companies, accounts for staff; roles for company admins) | 8305 | `nbpl_` |
| in-licensing | `/in-licensing` (coming soon) | 8306 | `nbil_` |
| pharmacy | `/pharmacy` | 8307 | `nbph_` |
| regulatory | `/regulatory` (coming soon) | 8308 | `nbrg_` |

Every table name starts with its app's prefix.

## Commands

From the repo root (needs only Node and uv):

```
npm run one                      # every API + the one app at http://localhost:4301 (sets up what's missing); Ctrl+C stops all
npm run bishnoi-crm              # one API alone (--setup: prepare only)
npm run bishnoi-one-app          # the screens only;  bishnoi-one-app:app opens them in a desktop window (desktop/)
npm run setup                    # prepare every app
```

In an app's `backend/`:

```
uv run main.py                                        # API with reload; docs at /docs
uv run pytest                                         # all tests
uv run pytest tests/test_deals.py::test_name -q       # one test
uv run alembic revision -m "what changed"             # new migration (migrations run automatically on start)
uv run python -m app.tools.users add --email … --name "…" --admin   # also: list, demo, password, disable, enable
uv run python -m app.tools.copy_database --to "<url>" [--company getmeds]
```

In `bishnoi-one-app/frontend/`: `npm run dev`, `npm run build`, `npx tsc --noEmit -p .`.

Keep the machine light: run one app at a time and only the tests affected by a change; don't run full suites or `tsc` across several apps in parallel.

## Architecture

**Backend** (`backend/app/`): `main.py:create_app(settings)` builds the FastAPI app; `server.py` is the Vercel entry point. Endpoints live in `routers/`; permissions are declared in `permissions.py` and enforced with `Depends(require("customers.edit"))` (`access.py`). Roles carry a scope (own / team / all records). Every change goes to the audit log (field names, never values), optionally mirrored to Discord. `guard.py` adds rate limits and plain-language errors; if the API can't start, every request answers 503 naming the setting to check. Command-line tools are in `app/tools/`.

**Multi-company (CRM, Inventory):** each company has its own database beside `DATABASE_URL` (`crm.db` → `crm-getmeds.db`; `neondb` → `neondb_getmeds`), opened lazily by `tenants.py`. The company comes from the session token's prefix. Locally `DEFAULT_COMPANY`/`DEV_COMPANIES` stand in for Platform registration.

**Tests:** `tests/conftest.py` builds a fresh SQLite database per test (`create_app` with test `Settings`) and seeds an Administrator (Ana) and a Salesperson (Ben). `TEST_DATABASE_URL` runs them on Postgres instead (it gets wiped).

**The one app** (`bishnoi-one-app/frontend`, see its README): the browser never calls an API. `src/platform/lib/modules.ts` lists the modules (path, API setting, Platform key). `proxy.ts` marks each request with its module from the path, so `src/platform/lib/api.ts` talks to that module's API with that module's session cookie (`bishnoi_<module>_session`). One Bishnoi One sign-in (`/login`, Platform `/identity/*`); a module's session is opened on first use from a Platform pass (`app/auth/enter/[module]`). The Admin Console (`/platform`) works on the account itself: Platform staff are recognised by email (`app/deps.py staff_by_account`). Module code is in `src/modules/<module>/` and pages under `app/(app)/<module>/` (Admin Console: `app/(app)/platform/`, its staff pages in `(staff)/`; public and print pages under `app/(bare)/`); every module draws with the shared kit `src/platform/` (UI in `ui/`): since 2026-10-26 the UI files in `src/modules/<module>/platform/` (sheet, field, button, pickers, icons, amount, dialogs, skeletons, bulk selection, formats, error screens…) are one-line re-exports of the shared ones, so a fix there reaches every module. What still differs per module stays in its copy: its API connection, types, labels, access, account and sign-in pieces, and marks/sparkline/avatar. Fix the shared component, not one screen; never re-copy a kit file into a module.

**Access (step R1, 2026-10-23):** roles are made once per company on the Platform (`app/access_roles.py`, `/identity/access`, screens `/platform/roles` and `/platform/roles/people`), one per person, with permissions and a scope per module; each API keeps declaring and enforcing its permissions and is sent the roles signed (`app/platform_roles.py`, the same in every API: `GET /platform/catalog`, `POST /platform/roles`).

The `bishnoi-one-app/frontend/AGENTS.md` note applies: this Next.js version differs from training data, so check `node_modules/next/dist/docs/` before using Next APIs.

**People (step R2, 2026-10-26):** people are added, given their one role and modules, given a password and switched off only on the Platform (`/identity/access/people`, the one app's `/platform/roles/people`, company administrators). Once an API is connected (`PLATFORM_API_URL` set) it refuses local user creation, passwords, role/name/email/status changes and role editing (`platform_roles.kept_on_platform`), closes its own password sign-in (`signs_in_here`: sign in with Bishnoi One only), and follows the Platform's switch-off (sessions end). Its role tables stay as the Platform's copy that every request is checked against; what is the module's own about a person (Finance e-signature/calendar, Pharmacy licence, CRM employee ID/teams) is still edited in the module. Unconnected (tests, standalone) everything works as before.

**Between apps:** Platform is the switchboard: accounts (one Bishnoi One sign-in), company registration, each app's address (Platform > Applications), connection keys and company services. Apps call each other API-to-API with `name:key` pairs, given to each app by the Platform (Connections), never typed (`INTEGRATION_KEYS` on the callee, `<APP>_API_URL`/`_KEY` on the caller only override it); CRM uses Inventory (products, stock), Finance (tax), Pharmacy (Rx quote checks). A missing link degrades the feature, it doesn't break the app.

**Deploying (2026-10-27):** the Platform needs only `DATABASE_URL`, every other API `DATABASE_URL` and `PLATFORM_API_URL`, the one app `PLATFORM_API_URL`. The rest defaults or lives in the Platform database: production is detected (Vercel, Coolify), `ALLOWED_HOSTS` defaults to any name in production, the signing key is kept in `nbpl_settings` (`passes.keep_in_database`), the first administrator is made on the one app's `/setup` (code in the Platform log, `app/setup.py`), the one app reads API addresses from `/public/applications`, and the CRM's email comes from the company's `smtp` service. Settings still override all of it.

## Repo workflow

- Everyone works on `main`, which holds every app and the one app. The per-app `bishnoi-<app>` branches and the Sync branches action were retired on 2026-10-24; don't create branches starting with `bishnoi-`.
- Pushing doesn't deploy. Deployment is by hand (the self-hosted Coolify server, Platform first; or the Vercel CLI per app) — the automated Deploy workflow was removed 2026-10-22.
- A new app is `bishnoi-<name>/` with `backend/` (no `frontend/`: its screens go in the one app as a new module), `.gitignore` and `README.md`; **Check apps** verifies this on PRs.
- `README.md` (setup, every `.env` setting per app) and `MAINTAINING.md` (actions, Vercel, linking apps, Discord) are the full references.

## Building features

- Build to `benchmarks/`: find the capability's row in `benchmark-matrix.md` first (an `open` row needs a decision before building), follow `patterns-to-adopt.md`, and update the row's "Ours today" with the change.
- UI is Ant Design in Poppins via the shared kit; fix the shared component rather than one screen. Wording is plain, sentence case, standard business terms.
- Main records carry a human `no` (from 40000001) beside the UUID `id`.
