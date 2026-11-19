# Bishnoi One: the one app

Every module's screens on one site, **one.bishnoi.ai** (decided 2026-10-23,
`benchmarks/decisions.md`). Every module's API is in the one backend
(`backend/`, since 2026-11-17), each under its path; this folder has only the
screens, and since 2026-10-24 it is the only place screens are.

The screens' server talks to the backend at `BACKEND_URL` (default
`http://127.0.0.1:8300`): a module's API is `BACKEND_URL` + its path
(`src/platform/lib/backend.ts`). Browsers never call the backend.

| Module | Path (screens and API) | Status |
|---|---|---|
| CRM | `/crm` | **here** (since 2026-10-23) |
| Inventory | `/inventory` | **here** (since 2026-10-23) |
| Finance | `/finance` | **here** (since 2026-10-23) |
| Pharmacy | `/pharmacy` | **here** (since 2026-10-23) |
| Executive Admin | `/admin` | **here** (since 2026-10-23) |
| Admin Console (Platform) | `/platform` (API `/platform`) | **here** (since 2026-10-24): a company's administration. One sign-in |
| Operations | `/operations` (API `/platform`) | **here** (since 2026-10-30): Bishnoi One's operators |
| In-Licensing | `/in-licensing` | coming soon |
| Regulatory | `/regulatory` | coming soon |

The list, and each module's status, is `frontend/src/platform/lib/modules.ts`.
Module code is in `frontend/src/modules/<module>/`, its pages under
`frontend/app/(app)/<module>/` (the console's under `app/(staff)/platform/console/`,
with its own bar; print pages and public links under `app/(bare)/`).

## Run it

From the repo root:

```
npm run one                    # everything: the one backend (every module's API) and these screens
npm run bishnoi-one-app        # the screens only, at http://localhost:4301 (the backend must be running)
npm run bishnoi-one-app:app    # the backend and the screens, in a desktop window
```

By hand, in `frontend/`: `npm run dev` (the backend running: `uv run main.py`
in `backend/`), `npm run build`, `npx tsc --noEmit -p .`.

`npm run one` prepares what's missing, starts the backend, then these screens
once it answers, and labels their output; Ctrl+C stops it all. Open http://localhost:4301 and sign in with your Bishnoi One account. You
see the modules your company has and you're granted, both set in the Platform
(Companies > the company's apps; People > the person's apps).

## How signing in works

1. You sign in once, with your Bishnoi One account (`/login`). The account's
   session is kept in an httpOnly cookie.
2. The first time you open a module, the server asks the Platform for a pass
   to it (the Platform decides who may open which module), and the module's API
   turns the pass into its own session (`app/auth/enter/[module]`).
3. Every request on a module's page goes to that module's API with its session
   (`src/platform/lib/api.ts`): the proxy marks the request with the module from
   its path, so module code calls `api.get(...)` as it always has.
4. Signing out, or into another company, drops every module's session.

Settings: `frontend/.env.example`.

## Roles and permissions (`/platform/roles`)

A company's administrators (Platform: People > company administrator) make
the company's roles once, for every module, and give each person one
(decided 2026-10-23, step R1). The Platform keeps them
(`backend/modules/platform/access_roles.py`) and sends each module the
roles and who holds them, signed, to `POST <api>/platform/roles`; each module
keeps them in its own role tables (`platform_roles.py`, the same file in
every module) and enforces them as before. Each sign-in pass carries the
person's role too, so a module that missed a change catches up.

- First time: **Bring in today's roles** takes each module's roles (the same
  name becomes one role) and gives each person theirs by email. Someone with
  different roles in different modules is listed to choose for; until then each
  module goes by the role it gave them.
- The modules' own Roles pages here send to it. Their Users pages stay for now
  (CRM teams and employee ids live there until teams move to the Platform).

## The Admin Console (`/platform`)

The Platform's screens in the one app, with the one Bishnoi One sign-in
(decided 2026-10-24; it replaced the separate staff console and its staff
login). Someone whose email is also a Platform staff account is that staff
member here (`backend/modules/platform/deps.py`, `staff_by_account`): Platform Admins
change, Support looks. They see **APIs** (each module's API, its status and
deployments), **Companies** and **Accounts**. A company's administrators see
**Roles** and **Role assignments**. Incidents, support, monitoring,
communications, connections and settings were left out.

## Hand-made details in the moved modules

The modules were moved in with a script on 2026-10-23 and 24 (it read the old
frontends, now gone). Inventory, Finance, Admin, Pharmacy and the console still
carry their own kit under `src/modules/<module>/platform/`, until they're
brought onto the shared one. Fixed by hand after the move:

- CRM: `lib/merged.ts` (`/crm/${path}`), the admin home's search (`/crm?q`),
  the new-quote breadcrumb, and `lib/page.ts` on the attention prompts, the bell,
  search and the quote's customer link;
- Admin: `lib/page.ts` (`adminPage`) on the home's attention and chart links;
- Inventory: `lib/links.ts` (`inventoryPage`) on the alerts in `platform/lib/api.ts` (`getFrame`);
- Admin Console: the console's APIs, Companies and Users (Accounts) pages
  under `app/(app)/platform/(staff)/`, links to its removed pages made plain
  text, and no address-following (that was for the old separate sites).

On this computer, every module asks the Platform (`BACKEND_URL/platform`) for
its pass key (`PLATFORM_PUBLIC_KEY` unset): a fixed key must be the running
Platform's.

## At cutover (one.bishnoi.ai)

- One deployment for the screens: this folder's `frontend/` (the old screens
  projects, one per app, go).
- Backend: `ONE_APP_URL=https://one.bishnoi.ai`.
- Platform console > Applications: each app's screens address becomes its path
  here (`https://one.bishnoi.ai/crm`, `/inventory`, `/finance`, `/admin`,
  `/pharmacy`, `/platform/console`; `/in-licensing`, `/regulatory`). The
  modules read these (the CRM links to Inventory's products with it). Done on
  this computer with `http://localhost:4301/...` on 2026-10-24.
- This app: `ONE_APP_URL=https://one.bishnoi.ai` and `BACKEND_URL` (the
  backend's internal address; see `frontend/.env.example`). The old per-module
  `*_API_URL` settings are no longer read.
- Backend: `CRM_APP_URL=https://one.bishnoi.ai/crm` (links in its emails, and
  the mailbox sign-in's return address: update that address in the Google and
  Microsoft apps used for mailboxes too).
