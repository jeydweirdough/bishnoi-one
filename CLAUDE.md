# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Bishnoi One: separate business apps (pharma distribution first; Philippines first) kept in one repo. Each `bishnoi-<app>/` folder is a complete, standalone app with `backend/` (Python 3.13, FastAPI, SQLAlchemy, Alembic, run with `uv`) and `frontend/` (Next.js 16 App Router, React 19, Ant Design 6, Tailwind 4). Apps do not import from each other; each has its own database, sign-in and settings.

| App | Screens | API | Table prefix |
|---|---|---|---|
| admin | 4300 | 8300 | `nbad_` |
| crm | 4302 | 8302 | `nbcm_` |
| finance | 4303 | 8303 | `nbfi_` |
| inventory | 4304 | 8304 | `nbin_` |
| platform | 4305 | 8305 | `nbpl_` |
| in-licensing | (API only) | 8306 | `nbil_` |
| pharmacy | 4307 | 8307 | `nbph_` |
| regulatory | (API only) | 8308 | `nbrg_` |

API port = screens port + 4000. Every table name starts with its app's prefix.

## Commands

From the repo root (needs only Node and uv):

```
npm run bishnoi-crm              # API + screens together (sets up .env, .venv, node_modules if missing)
npm run bishnoi-crm -- --api     # API only   (--web: screens only, --setup: prepare only)
npm run bishnoi-crm:app          # in its own desktop window (desktop/ Electron shell)
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

In an app's `frontend/`: `npm run dev`, `npm run build`, `npm run lint`.

Keep the machine light: run one app at a time and only the tests affected by a change; don't run full suites or `tsc` across several apps in parallel.

## Architecture

**Backend** (`backend/app/`): `main.py:create_app(settings)` builds the FastAPI app; `server.py` is the Vercel entry point. Endpoints live in `routers/`; permissions are declared in `permissions.py` and enforced with `Depends(require("customers.edit"))` (`access.py`). Roles carry a scope (own / team / all records). Every change goes to the audit log (field names, never values), optionally mirrored to Discord. `guard.py` adds rate limits and plain-language errors; if the API can't start, every request answers 503 naming the setting to check. Command-line tools are in `app/tools/`.

**Multi-company (CRM, Inventory):** each company has its own database beside `DATABASE_URL` (`crm.db` → `crm-getmeds.db`; `neondb` → `neondb_getmeds`), opened lazily by `tenants.py`. The company comes from the session token's prefix. Locally `DEFAULT_COMPANY`/`DEV_COMPANIES` stand in for Platform registration.

**Tests:** `tests/conftest.py` builds a fresh SQLite database per test (`create_app` with test `Settings`) and seeds an Administrator (Ana) and a Salesperson (Ben). `TEST_DATABASE_URL` runs them on Postgres instead (it gets wiped).

**Frontend:** the browser never calls the API. Pages and server actions (`src/actions/*.ts`, `"use server"`) call it from the Next server via `src/platform/lib/api.ts`, with the token in an httpOnly cookie; `proxy.ts` gates pages without a session. Routes in `app/(app)/…/page.tsx` are thin re-exports of screens in `src/screens/`. `src/platform/` is the shared shell, UI kit (`ui/`: dialog, pickers, file-drop, skeleton, field…), session and API client. It is **copied into each app, not shared**, and the copies have drifted; a change meant for every app has to be made in each copy.

The `frontend/AGENTS.md` note applies: this Next.js version differs from training data, so check `node_modules/next/dist/docs/` before using Next APIs.

**Between apps:** Platform is the switchboard: accounts (one Bishnoi One sign-in), company registration, each app's address (Platform > Applications), connection keys and company services. Apps call each other API-to-API with `name:key` pairs (`INTEGRATION_KEYS` on the callee, `<APP>_API_URL`/`_KEY` on the caller); CRM uses Inventory (products, stock), Finance (tax), Pharmacy (Rx quote checks). A missing link degrades the feature, it doesn't break the app.

## Repo workflow

- `main` holds every app; `bishnoi-<app>` branches hold one app each and are kept in sync by the **Sync branches** action. Don't create branches starting with `bishnoi-`, and don't PR an app branch into `main`.
- Pushing doesn't deploy. Deployment is by hand (the self-hosted Coolify server, Platform first; or the Vercel CLI per app) — the automated Deploy workflow was removed 2026-10-22.
- A new app is `bishnoi-<name>/` with `frontend/`, `backend/`, `.gitignore`, `README.md`, `GIT-GUIDE.md` and an unchanged copy of `.github/workflows/sync-branches.yml`; **Check apps** verifies this on PRs.
- `README.md` (setup, every `.env` setting per app) and `MAINTAINING.md` (actions, Vercel, linking apps, Discord) are the full references.

## Building features

- Build to `benchmarks/`: find the capability's row in `benchmark-matrix.md` first (an `open` row needs a decision before building), follow `patterns-to-adopt.md`, and update the row's "Ours today" with the change.
- UI is Ant Design in Poppins via the shared kit; fix the shared component rather than one screen. Wording is plain, sentence case, standard business terms.
- Main records carry a human `no` (from 40000001) beside the UUID `id`.
