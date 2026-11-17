# One backend, made of modules

Date: 2026-11-17. Owner's decision: "not app-based". The eight `bishnoi-<app>/backend` APIs become modules of **one** backend: one server, one deploy, one place to read the code.

## Today

| Folder | Python files | Routers | Migrations | Tests |
|---|---|---|---|---|
| bishnoi-platform | 77 | 27 | 29 | 37 |
| bishnoi-crm | 114 | 42 | 83 | 67 |
| bishnoi-inventory | 78 | 24 | 24 | 36 |
| bishnoi-finance | 116 | 31 | 36 | 93 |
| bishnoi-admin | 42 | 10 | 11 | 19 |
| bishnoi-pharmacy | 44 | 17 | 7 | 16 |
| bishnoi-in-licensing, bishnoi-regulatory | 18 each | 4 | 2 | 4 |

- Every backend has the same stack: Python 3.13, FastAPI, SQLAlchemy and psycopg; Finance also uses pg8000. Each has its own Alembic history with its own version table (`nbcm_alembic_version`, …).
- Every table already starts with its module's prefix (`nbcm_`, `nbin_`, `nbfi_`, …), so all modules can share one database without clashes. On the server they already share one PostgreSQL.
- The modules call each other over HTTP:
  - `platform_api_url`: 56 places (sign-in passes, roles, the org chart, events);
  - Inventory: 3; Finance: 3; Pharmacy, orders and CRM: 1 each.
- Every package is named `app`, so two of them can't be imported into one Python process. This is the main thing to change.

## Target

```
backend/
  pyproject.toml          one set of dependencies
  main.py                 one FastAPI: mounts every module
  modules/
    platform/  crm/  inventory/  finance/  admin/  pharmacy/  in_licensing/  regulatory/
      (each: routers, models, migrations, tests; package name = module name)
  shared/                 later: what every module copies today (recycle bin, events, platform_roles, guard, audit)
```

## Stages (each stage ships on its own, behaviour unchanged unless stated)

**M0. Checkpoint.** Commit Step 1 (the removed features) before anything moves.

**M1. One process, same behaviour.**
- Move `bishnoi-<x>/backend/app` to `backend/modules/<x>` and rewrite `from app.` to `from modules.<x>.`. This is done by a script, so it is repeatable and reviewable.
- `backend/main.py` mounts each module's existing `create_app()` at `/platform`, `/crm`, `/inventory`, …. Each module keeps its own middleware, errors, sessions and permissions.
- Migrations: on start, each module still runs its own Alembic history, with its own version table. The live database needs nothing new.
- Settings: one `DATABASE_URL`. A module-specific override is allowed for local SQLite (`CRM_DATABASE_URL`, …).
- The one app's API addresses all point at the one backend, with the module path added.
- Order, smallest first, to prove the pattern: in-licensing and regulatory → admin → pharmacy → inventory → crm → platform → finance last.
- **Finance check:** the golden accounting scenario must give the same output before and after.
- **Deploy:** one Coolify app replaces eight. The old folders, per-app `.env` files, the Vercel files, `deploy.mjs`, `run-app.mjs` and the "What to redeploy" and "Check apps" workflows are removed.

**M2. Modules call each other directly.**
- Replace the HTTP calls with direct function calls: CRM to Inventory (products, stock), CRM to Finance (tax), Finance to Inventory (costs), and events delivered in-process.
- Connection keys between modules go away. Everything else still behaves the same.

**M3. One sign-in session.**
- One session cookie for the whole system, instead of a session per module plus Platform passes. Employees, roles and the org chart live once (Platform), and modules read them directly. The per-module user and role copies become read-only, then are dropped.
- Behaviour visible to users: one sign-in, no "Opening CRM…" between areas.
- Built 2026-11-18, first part (what users see): signing in, or moving to another company, opens every part the person may open at once (`bishnoi-one-app/frontend/src/platform/lib/module-session.ts` `openEveryPart`, called by `src/one/actions.ts`); `app/auth/enter` is only the fallback for a session that ran out; no "Opening X…" loader. Not yet: one session cookie read by every module, and dropping the per-module user copies (after M2, when modules read the Platform directly).

**M4. One menu by work** (plan Step 4G). Built 2026-11-18 (owner agreed the preview Desktop/bishnoi-one-menu-by-work.html with its recommendations):
- One sidebar for everybody, built from the account (`bishnoi-one-app/frontend/src/one/menu/one-menu.ts`, given by `app/(app)/layout.tsx`, drawn by the shared `src/platform/shell/sidebar.tsx`): Home, Customers, Selling, Field, Stock, Buying, Deliveries, Money, Accounting, Pharmacy, Office, Team, Reports; Admin and (operators) Operations at the foot. Every page keeps its address.
- A group lists only what the role allows in the module keeping the page: Platform `/identity/me` `apps[].permissions` (null = every page there). Pages still check.
- No module switcher, no app grid at the top right, breadcrumbs Company / Group / Page. One Home (`/`, the person's groups and pages) and one Reports page (`/reports`, each part's Reports Center).
- Pages that exist twice (CRM products and Inventory items, vendors and suppliers, two sales order lists, two calendars) are placed as they are; merging is Step 3. Promotional materials are one row opening the person's step.
- Each module's own `nav.tsx` now only lends its red "not set up" marks, matched by address.

## Rules while moving

- Finance posting, numbering, approvals, void and reissue, and the voucher release rule move unchanged; the golden check runs at every stage.
- No database data moves: same tables, same version tables.
- Each module's tests run on their own (`uv run pytest modules/crm/tests`), one module at a time.
- Nothing is deployed until the owner says so. At cut-over, take a database backup, then stop eight containers and start one.
