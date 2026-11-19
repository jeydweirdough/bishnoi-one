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
- Built 2026-11-18 (not deployed). How: `backend/modules/inprocess.py`. `backend/main.py` registers each module's app as it starts (key, path); a call to `BACKEND_URL` + a registered path is handed to that app as an ASGI request, on its own event loop in its own thread (safe from sync and async routes and background threads), and answered with an `httpx.Response` (or a urllib-style response / `HTTPError` for the callers that use urllib). Same routes, payloads, checks and signed passes; only the network is gone. Any other address, and everything while nothing is registered (each module's tests, a module run alone), still goes over HTTP unchanged.
- Trust without keys: an in-process request carries `scope["bishnoi.internal"]` = the caller's Platform key (crm, finance, exec…). Only `inprocess.py` sets it; the front door (`modules/dispatch.py`, moved out of main.py) takes it out of every outside scope, and no header is read for it. Each module's key check takes it as that app: `calling_app` in CRM, Inventory, Finance and Pharmacy (X-Bishnoi-Key) and the Platform's `links.app_of_request` for `/connect/links`, `/connect/events`, `/connect/services`, `/connect/signature` (X-Bishnoi-App-Key). A link needs its address only (`inprocess.linked`: CRM inventory/finance/orders/pharmacy_linked, Finance crm/inventory_linked, Admin `linked`); the key header is sent only when there is one.
- Call sites now through it: CRM to Inventory, Finance (tax, prices), Pharmacy, orders; Finance to CRM and Inventory; Admin to CRM and Pharmacy; every module to the Platform (pass key, hello, links, events, services, signature, company pass); the Platform to the modules (roles notes, catalog, roles export, company pass, events and flush, connect-key delivery, health checks).
- Connections: two modules of the one backend are linked without keys (`links.built_in_pair`: state working, no waiting for connect keys; `/connect/links` lists the link even without a readable key; `builtIn` on links, `inBackend` on applications; the Operations application page says "Built in"). A link switched off is still off. Key code stays for modules outside the one backend and for the cut-over; delivered connect keys still arrive (now in-process) and still work.
- Checked: new `modules/platform/tests/test_inprocess.py` (CRM reads Inventory's products and Finance its costs with no keys, from sync and async routes; an event from Finance taken by the Platform with no connect key and delivered signed to the CRM in-process; an outside request with the mark as a header or planted in the scope gets 401). The real backend booted with every module started and no startup warning; with nothing listening, CRM→Inventory products (104), Finance→Inventory costs, Finance→CRM prices and Platform→CRM health all answered in-process.
- Left on HTTP, on purpose: calls outside Bishnoi One (Zoho, Discord, OpenStreetMap, mail), and a module whose address is set to a server of its own. Not yet: dropping the keys, links and connect-key code (after the cut-over), and calling functions instead of routes (the routes keep each module's own checks for now).

**M3. One sign-in session.**
- One session cookie for the whole system, instead of a session per module plus Platform passes. Employees, roles and the org chart live once (Platform), and modules read them directly. The per-module user and role copies become read-only, then are dropped.
- Behaviour visible to users: one sign-in, no "Opening CRM…" between areas.
- Built 2026-11-18, first part (what users see): signing in, or moving to another company, opened every part the person may open at once (`openEveryPart`); no "Opening X…" loader. Replaced the same day by the second part.
- Built 2026-11-18, second part (one session): the one app sends the Bishnoi One account's own session token (`bishnoi_account` cookie) to every module (`bishnoi-one-app/frontend/src/platform/lib/api.ts`). Each module (CRM, Inventory, Finance, Executive Admin, Pharmacy; `deps.py`) takes it when it runs in the one backend: it asks the Platform in-process `GET /platform/internal/session?app=<its key>` (`modules/platform/routers/identity.py` `internal_session`; answered only to a request carrying the in-process mark, and only about the module asking: 404 otherwise) who the token is. The answer is what a pass would say (`passes.person_claims`: person, company, role spec with permissions and scope, org placement, company administrator) and is refused exactly as a pass is (`may_open`, shared with `/identity/pass`: sign-in ended or revoked, account or company suspended, module not the company's or not given to the person, handed-over password, two-step owed). The module finds or adds the person with the same code as its pass sign-in (`routers/auth.py` `user_from_claims`) and keeps a session row of its own for the token (hashed with an `account:` prefix, so its records, "last signed in", Finance's recent-sign-in check, sign-out and View as work as before). CRM and Inventory take the company from the Platform's answer, not the token prefix. Shared code: `backend/modules/one_session.py`; answers kept 60 s per module and token, dropped at once on sign-out, company switch and any password change (the Platform calls `one_session.forget`), never kept when refused.
- The proxy no longer opens module sessions, and sign-in no longer opens every part (`openEveryPart` removed): with one backend and one app deployed together that would only make sessions nobody uses. Fallback kept for a half-upgraded deployment: a module answering 401 to the account token is asked again with its own session cookie, and `app/auth/renew` → `app/auth/enter` still opens that cookie from a pass (Admin Console soft opening, `src/platform/lib/enter.ts`, is no longer needed by its two pages but kept).
- Not dropped: each module's user and role tables. Every record points at them (owners, approvers, audit), so they stay as the read-only copy the Platform keeps in step (roles pushed signed, people provisioned from the Platform's answer, local edits refused while connected: `platform_roles.kept_on_platform`). Each module's own password sign-in and `/auth/platform` stay for a module run alone. In-Licensing and Regulatory (coming soon) have no sign-in yet.

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
