# Bishnoi One: the one app

Every module's screens on one site, **one.bishnoi.ai** (decided 2026-10-23,
`benchmarks/decisions.md`). Each module keeps its own API and database in its
own folder (`bishnoi-crm/backend`, `bishnoi-finance/backend`…); this folder
has only the screens, and since 2026-10-24 it is the only place screens are
(the per-app frontends were removed).

| Module | Path | API (on this computer) | Status |
|---|---|---|---|
| CRM | `/crm` | 8302 | **here** (since 2026-10-23) |
| Inventory | `/inventory` | 8304 | **here** (since 2026-10-23, its own kit) |
| Finance | `/finance` | 8303 | **here** (since 2026-10-23, its own kit) |
| Pharmacy | `/pharmacy` | 8307 | **here** (since 2026-10-23, its own kit) |
| Executive Admin | `/admin` | 8300 | **here** (since 2026-10-23, its own kit) |
| Admin Console (Platform) | `/platform` | 8305 | **here** (since 2026-10-24): APIs, companies and accounts for Bishnoi One's staff; roles and role assignments for a company's administrators. One sign-in |
| In-Licensing | `/in-licensing` | 8306 | coming soon |
| Regulatory | `/regulatory` | 8308 | coming soon |

The list, and each module's status, is `frontend/src/platform/lib/modules.ts`.
Module code is in `frontend/src/modules/<module>/`, its pages under
`frontend/app/(app)/<module>/` (the console's under `app/(staff)/platform/console/`,
with its own bar; print pages and public links under `app/(bare)/`).

## Run it

From the repo root:

```
npm run one                    # everything: the Platform's and each module's API, and these screens
npm run bishnoi-one-app        # the screens only, at http://localhost:4301
```

`npm run one` prepares what's missing, starts the Platform's API (the sign-in),
each live module's API and these screens, and labels their output; Ctrl+C stops
it all. Open http://localhost:4301 and sign in with your Bishnoi One account. You
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
(`bishnoi-platform/backend/app/access_roles.py`) and sends each module the
roles and who holds them, signed, to `POST <api>/platform/roles`; each module
keeps them in its own role tables (`app/platform_roles.py`, the same file in
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
member here (Platform `app/deps.py`, `staff_by_account`): Platform Admins
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

On this computer, Finance's and Pharmacy's APIs ask the Platform for its pass
key (their `PLATFORM_PUBLIC_KEY` is commented out): a fixed key must be the
running Platform's.

## At cutover (one.bishnoi.ai)

- One deployment for the screens: this folder's `frontend/` (the old screens
  projects, one per app, go).
- Platform API: `ONE_APP_URL=https://one.bishnoi.ai`.
- Platform console > Applications: each app's screens address becomes its path
  here (`https://one.bishnoi.ai/crm`, `/inventory`, `/finance`, `/admin`,
  `/pharmacy`, `/platform/console`; `/in-licensing`, `/regulatory`). The
  modules read these (the CRM links to Inventory's products with it). Done on
  this computer with `http://localhost:4301/...` on 2026-10-24.
- This app: `ONE_APP_URL=https://one.bishnoi.ai`, `PLATFORM_API_URL` and each
  module's `<MODULE>_API_URL` (see `frontend/.env.example`).
- CRM API: `CRM_APP_URL=https://one.bishnoi.ai/crm` (links in its emails, and
  the mailbox sign-in's return address: update that address in the Google and
  Microsoft apps used for mailboxes too).
