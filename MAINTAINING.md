# Looking after the Bishnoi One repo

This page is for the repo owner. Everyone else only needs
[README.md](README.md).

---

## Adding people

Repo → **Settings → Collaborators → Add people**. They get an email
invitation, and can push once they accept it. Point them to the README.

---

## One-time GitHub setup for the actions

Everyone works on `main`. The repo has one action, in `.github/workflows/`:

| Action | Runs when | What it does |
|---|---|---|
| **Check apps** (`check-apps.yml`) | every pull request into `main` | Checks the one backend's layout: each `backend/modules/<module>` has `__init__.py`, `main.py`, `config.py`, `alembic.ini`, `migrations/versions/`, `tests/` and `README.md`, is started by `backend/main.py`, and every table it declares starts with its prefix; no per-app API folders (`bishnoi-<x>/backend`) or screens outside the one app; no secrets or local data committed. |

There is no deploy action: deployment is by hand ([below](#putting-it-online-coolify)). The per-app
"What to redeploy" action and the Vercel deploy scripts were removed on 2026-11-17, when the eight APIs
became one backend.

Set this once:

1. **Optional: make the check required.** Settings → Branches → add a rule
   for `main` → "Require status checks to pass" → pick **check**. Then a
   pull request can't be merged while the check is red.

---

## Reviewing a new module

Someone proposes a new module as a pull request from an `add-module/<name>`
branch into `main` (README section 8). Before merging:

1. **Check apps is green.**
2. **The module's name and path are the ones you want.** Renaming later means
   changing its package, its path in `backend/main.py`, the one app and the
   Platform's Applications.
3. **Its table prefix is new** and in `PREFIXES` in `check-apps.yml`; its
   migrations use their own version table (`<prefix>alembic_version`).
4. **Nothing is committed that shouldn't be:** no `.env`, no `node_modules/`,
   no `.venv/`, no database files.
5. **It meets the benchmark** ([`benchmarks/`](benchmarks/README.md)): each
   feature it adds follows its row's decision in `benchmark-matrix.md` (an
   `open` row needs deciding first) and the rules in `patterns-to-adopt.md`,
   and its "Ours today" cells are filled in.

Then **merge** it, add the module to the tables in `README.md`, and delete
the `add-module/<name>` branch.

---

## Putting it online (Coolify)

Bishnoi One runs on the office server in Coolify as **two applications** built
from this repo, plus PostgreSQL. Nothing deploys by itself: pushing to `main`
does not deploy. When you're ready, open the application in Coolify and press
**Redeploy**, **the backend first**, then the one app. Watch the deployment
log; a module that can't start answers 503 under its path naming the setting
to check, and the others run (`/health` lists which started).

**1. The backend** (every module's API)

| Coolify field | Value |
|---|---|
| Build pack | Railpack (Nixpacks works too): Python with uv, from `pyproject.toml` / `uv.lock` |
| Base directory | `backend` |
| Start command | `uv run uvicorn main:app --host 0.0.0.0 --port 8300` |
| Ports Exposes | `8300` |
| Domain | none: internal only, reached at its internal address (e.g. `http://10.0.1.1:8300`) |
| Health check | `GET /health` |

| Environment variable | Value |
|---|---|
| `DATABASE_URL` | The PostgreSQL database every module shares (Coolify's internal URL, e.g. `postgresql://…@…:5432/bishnoione`). CRM and Inventory make a database per company beside it (`bishnoione_getmeds`). |
| `BACKEND_URL` | The backend's internal address, e.g. `http://10.0.1.1:8300`, no `/` at the end. Every module is at `BACKEND_URL` + its path; the Platform hands these addresses out. |
| `ONE_APP_URL` | `https://one.bishnoi.ai` (the one app's public address). |

Worked out by themselves, and still settable to override: `ENVIRONMENT`
(production on Coolify), `ALLOWED_HOSTS` (any name in production),
`PASS_SIGNING_KEY` (made on the first start and kept in the database, so keep
the database's backups as safe as the server's settings), the first
administrator (the one app's `/setup` page), every module's `*_API_URL`
(`BACKEND_URL` + path), the keys between modules (from the Platform's
Connections), and the CRM's email (the company's Email sending service). A
setting for one module only is written with its prefix: `CRM_…`,
`FINANCE_…` (README section 6).

**2. The one app** (every module's screens)

| Coolify field | Value |
|---|---|
| Base directory | `bishnoi-one-app/frontend` |
| Build / start | `npm run build` / `npm run start` |
| Ports Exposes | `4301` |
| Domain | `https://one.bishnoi.ai` (through the Cloudflare tunnel) |

| Environment variable | Value |
|---|---|
| `BACKEND_URL` | The backend's internal address, e.g. `http://10.0.1.1:8300`. |
| `ONE_APP_URL` | `https://one.bishnoi.ai` |

Remove the old per-module addresses from the one app (`PLATFORM_API_URL`,
`CRM_API_URL`, `INVENTORY_API_URL`, `FINANCE_API_URL`, `ADMIN_API_URL`,
`PHARMACY_API_URL`…): the one app no longer reads them.

**3. Check**: `GET <BACKEND_URL>/health` shows every module `true`; the one
app's `/login` opens; signing in opens CRM, Inventory and Finance; in the CRM,
Products shows Inventory's stock (the CRM → Inventory link).

### Moving from eight applications to one (once)

Until 2026-11-17 each module was its own Coolify application (Platform, CRM,
Inventory, Finance…, ports 8300–8308). To move to the one backend:

1. **Back up the database first** (all of it, the per-company databases too),
   e.g. `pg_dumpall` from the PostgreSQL container, or Coolify's backup, and
   check the file isn't empty.
2. **Write down every old application's environment variables.** Settings the
   old applications shared (same name, same value) go once into the backend's
   variables. One that differed between them goes in with the module's prefix,
   e.g. the Platform's `PASS_SIGNING_KEY` stays `PASS_SIGNING_KEY` (only the
   Platform has it), but two different `INTEGRATION_KEYS` become
   `CRM_INTEGRATION_KEYS` and `FINANCE_INTEGRATION_KEYS`. Keep
   `PASS_SIGNING_KEY` exactly as it was if the Platform had one: passes and
   the sealed keys between modules depend on it. Drop every old address
   (`PLATFORM_API_URL`, `INVENTORY_API_URL`, `CRM_API_URL`… with ports
   830x): `BACKEND_URL` replaces them.
3. **Create the backend application** (above) and deploy it while the old ones
   still run: it uses the same tables and the same migration histories, so it
   needs nothing new in the database. Check `/health`.
4. **Point the one app at it**: set `BACKEND_URL`, remove the old
   `*_API_URL` variables, redeploy the one app, and check sign-in and a few
   pages in each module.
5. **Stop the eight old applications** (Platform, CRM, Inventory, Finance,
   Admin, Pharmacy, In-Licensing, Regulatory). Keep them stopped, not deleted,
   for a week in case you need to go back (start them again and put the one
   app's old variables back).
6. Nothing to change on Platform > Applications: the addresses registered
   there for each module are no longer used; the Platform reports
   `BACKEND_URL` + each module's path instead. The connect keys and links stay
   as they are (they're kept in the database).

---

## Linking the CRM to Inventory

> Not needed when the modules are connected to the Platform (2026-10-27): the link and its key are
> made on its Connections page, and the address is `BACKEND_URL` + the module's path. These steps are
> for the backend running without the Platform: settings go in `backend/.env`, with the module's prefix.

The CRM's products come from Inventory, with their SRP, and it shows
Inventory's stock on Products and on new quotes. The two modules talk through a
shared key. Set up once, in `backend/.env` (or the backend's environment), then
restart the backend:

1. Make a key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. **Inventory:** `INVENTORY_INTEGRATION_KEYS` = `["crm:<the key>"]`.
3. **CRM:**
   - `CRM_INVENTORY_API_KEY` = the key (the address is `BACKEND_URL` +
     `/inventory` by itself).
   - `CRM_INVENTORY_APP_URL` = Inventory's screens, for the "Add it in Inventory"
     button (optional, e.g. `https://one.bishnoi.ai/inventory`).

Afterwards:

- Products are added and changed in Inventory. The CRM brings the list over
  every 15 minutes, when someone opens Products or a new quote, or at once
  with **Sync now** on Products. It matches products by SKU = product code.
  A product the CRM had before the link, with the same code, is taken over
  rather than copied.
- The SRP comes from Inventory's selling price, as the CRM's **SRP** price
  type. Each team (division) can still quote its own price over it under
  **Products → Special prices**. The other price types are still set in the
  CRM.
- A product discontinued in Inventory, or removed there, is switched off in
  the CRM, not deleted: old quotes keep it.
- Without these settings, the CRM keeps its own product list, as before.

To change the key, add the new one to `INTEGRATION_KEYS` next to the old one
(`["crm:<new>", "crm:<old>"]`), switch the CRM to the new one, then remove the
old one.

---

## Linking the CRM to Finance

> Not needed when the modules are connected to the Platform (2026-10-27): the link and its key are
> made on its Connections page, and the address is `BACKEND_URL` + the module's path. These steps are
> for the backend running without the Platform: settings go in `backend/.env`, with the module's prefix.

Finance works out the tax on CRM quotes (the Philippines: VAT, exempt,
zero-rated, senior citizen and PWD), as the last step of the CRM's price
rules.

1. Make a key, as above. Use a different one from the Inventory link.
2. **Finance:** `FINANCE_INTEGRATION_KEYS` = `["crm:<the key>"]`.
3. **CRM:** `CRM_FINANCE_API_KEY` = the key (the address is `BACKEND_URL` +
   `/finance` by itself).
4. Restart the backend. In Finance, an admin fills in **Tax → Registration** (VAT
   status, registered name, TIN and address, as the invoice shows them).
5. In the CRM, an admin ticks **Add tax from Finance** under **Settings →
   Price rules** and saves. The box stays greyed out until the CRM has
   `FINANCE_API_URL` and `FINANCE_API_KEY`.

Afterwards:

- Each quote shows the invoice's tax summary (VATable sales, VAT, amount due)
  and keeps it, so a later rate change doesn't alter old quotes.
- Each product's VAT category (standard, zero-rated, exempt) is set on the
  CRM's product page. Existing products start as standard.
- If Finance can't be reached, the quote isn't saved and the rep is told to
  try again. Untick the box to quote without tax.

The same link carries **marketing requests** (cash advances):

- **In the CRM:** a salesperson or field agent submits a request, and their
  Team Lead approves or declines it (**Field work → Marketing requests**). An
  admin sets the purposes, and whether each is subject to liquidation, under
  **Settings → Marketing request purposes**.
- **In Finance:** an approved request goes to Finance (**Marketing requests**),
  which releases the cash advance (*For release*), reviews the liquidation
  expense by expense (*For review*), and records the refund due from the
  employee or the reimbursement due to them (*For settlement*). Released
  advances not yet liquidated are under *Outstanding*; settled and cancelled
  requests under *History*.
- **Expense categories:** Finance's admin manages the categories and
  sub-categories (Food › Dining) under **Accounting**. Each category posts to
  an expense account, and only reimbursable ones are charged to the company.
- **Accounting:** every step that moves money posts a balanced journal entry.
  Accounting has the journal entries (with manual journals and reversals),
  the chart of accounts, account ledgers, the trial balance, the expense
  categories, and the default accounts the automatic entries use.
- **If Finance is down:** an approval made while Finance can't be reached
  waits in the CRM, and is sent the next time anyone opens it.

Finance's demo admin is Rhea Castillo (`rhea@pharmacrm.test`, demo1234). The
admin changes the chart of accounts, expense categories, default accounts and
tax setup; Finance Staff (Joy, Fely) do everything else.

---

## Linking the CRM to Pharmacy

> Not needed when the modules are connected to the Platform (2026-10-27): the link and its key are
> made on its Connections page, and the address is `BACKEND_URL` + the module's path. These steps are
> for the backend running without the Platform: settings go in `backend/.env`, with the module's prefix.

Pharmacy checks that orders are compliant. A CRM quote marked **Rx** can't be
ordered until a pharmacist in Pharmacy verifies its prescription.

1. Make a key, as above. Use a different one from the other links.
2. **Pharmacy:** `PHARMACY_INTEGRATION_KEYS` = `["crm:<the key>"]`.
3. **CRM:** `CRM_PHARMACY_API_KEY` = the key (the address is `BACKEND_URL` +
   `/pharmacy` by itself).
4. Restart the backend.

How it works:

- **In the CRM:** an Rx quote shows a **Pharmacist check** section. The rep
  enters the prescription (prescriber, licence number, date, clinic) and
  sends it. **Raise order** stays off until the pharmacist verifies it.
- **In Pharmacy:** the quote arrives in **Prescriptions → Inbox**, marked
  "From Bishnoi One CRM · Q-…". The pharmacist checks it as any other
  prescription. It isn't dispensed in Pharmacy: the CRM's order fills it.
- **The verdict goes back:** verified (the quote can be ordered), needs
  clarification (the rep corrects the details and sends it again, to the same
  check), or rejected (final; the quote can't be ordered).
- The CRM asks Pharmacy for the verdict whenever someone opens the quote, at
  most every 30 seconds. If Pharmacy can't be reached, the quote shows the
  last answer and says why.

Other apps can use the same check. `POST /integration/checks` sends an order
(customer, prescription, lines by product code) and `GET
/integration/checks/{sourceId}` reads the verdict, with the header
`X-Bishnoi-Key`. The fields are in
`backend/modules/pharmacy/routers/integration.py`. Give each app its own
entry in `INTEGRATION_KEYS`, e.g. `["crm:<key>", "orders:<key>"]`.

---

## Linking the CRM to Bishnoi One Order

Bishnoi One Order is its own application. On a quote, **Raise order** sends the quote
to it; the CRM keeps the order number it answers with, so a quote is ordered
once. The button is off until the quote is approved and its guarantee letter is
checked.

In the backend's settings, for the CRM:

| Variable | Value |
|---|---|
| `CRM_ORDERS_API_URL` | Bishnoi One Order's API, e.g. `https://orders-api.example.com` |
| `CRM_ORDERS_API_KEY` | The key Bishnoi One Order gave the CRM |

The CRM calls `POST {ORDERS_API_URL}/orders` with the headers `X-Bishnoi-Key`
and `Idempotency-Key` (the quote's id, the same on a retry), and expects
`{"id", "number"}` back, with an optional `"url"` for the "Order SO-..." link.
The payload is described at the top of `backend/modules/crm/orders.py`; to
see it for a real quote, call `GET /crm/quotes/{id}/order-payload` on the backend.

The printed quotation (**Print** on a quote) takes its letterhead from
Settings, Company and quotes: business address, TIN, and phone or email.

## One Bishnoi One account for every app (the platform)

People at the client companies sign in once, with their Bishnoi One account on
Bishnoi One Platform, and open each application their company has and they have
been given (Platform > Users > their applications and role). The platform
gives a signed, two-minute pass for one application; the application checks
it with the platform's public key, takes it once, and opens its own session
with the role from the platform. Apps: Executive Admin (`exec`), CRM,
Finance, Inventory, Pharmacy. Each keeps its own password sign-in as well.

To set it up:

1. Nothing to make: the Platform makes its key pair on its first start and
   keeps it in the database (`PASS_SIGNING_KEY` overrides it; to make one by
   hand, `uv run python -m modules.platform.passes` in `backend/`).
2. Every module finds the Platform at `BACKEND_URL` + `/platform` and fetches
   the public half from its `/pass/key`, and again when the key is replaced;
   `PLATFORM_PUBLIC_KEY` is only for pinning it.
3. The screens are the one app: one Bishnoi One sign-in there opens every
   module, and roles are managed centrally in the Admin Console. Its
   `BACKEND_URL` = the backend (see
   [bishnoi-one-app/README.md](bishnoi-one-app/README.md)).
4. Platform > Applications: each application's screens address (where it
   opens, e.g. `https://one.bishnoi.ai/crm`): the pass goes back only there.
   Its API address is worked out (`BACKEND_URL` + its path).
6. Platform > Users > a person > the key icon: makes their first password,
   shown once. They change it after signing in.

A person gets a pass only while their account and their company are active,
the company has the application, and they have been given it. A new person
in an app is added with the platform's role; a role the app doesn't have is
refused, except in Finance, where it becomes Finance Staff (an application
admin is the Administrator there).

## Connecting Discord

Discord is where **announcements** are kept, and where **every app's log**
goes, the way the Getmeds orders app kept its orders there
(`app/discord.py`, the same file in every backend).

- **Announcements** are written in Platform (Communications). Each one is a
  thread in the announcements channel, named with its id,
  `ANN-YYYYMMDD-NNNN` (numbered from 0001 each day, Manila time), holding
  the announcement as JSON in one message that's edited on every change. On
  start, Platform reads the channel back. Every app shows the ones for it,
  and for everyone, above every page.
- **Logs**: each app posts a thread a day in the logs channel,
  `LOG-CRM-20260926`, `LOG-FINANCE-20260926`…, one line per change: what,
  to what, who, when. Never values or passwords. The CRM, Inventory,
  Pharmacy and Platform send their audit log. Admin, Finance, In-Licensing
  and Regulatory have none yet, so they send every change and sign-in.

Set up once:

1. Make two channels, e.g. `#bishnoi-announcements` and `#bishnoi-logs`. Keep
   them private: only people who may read the logs.
2. In each, **Edit Channel → Integrations → Webhooks → New Webhook**, and
   copy its URL. The announcements one goes in Platform's
   `DISCORD_ANNOUNCEMENTS_WEBHOOK_URL`; the logs one in
   `DISCORD_LOGS_WEBHOOK_URL` (every module). Don't use one channel for both.
3. In the [Discord Developer Portal](https://discord.com/developers/applications),
   **New Application** → **Bot** → **Reset Token**: that's
   `DISCORD_BOT_TOKEN`, the same in every app. On the same page, turn on
   **Message Content Intent** and save; without it Discord gives the
   messages back blank.
4. **OAuth2 → URL Generator**: tick `bot`, then **View Channels**, **Read
   Message History**, **Create Public Threads** and **Send Messages in
   Threads**. Open the URL and add the bot to the server, with access to both
   channels.
5. In `backend/.env` (on the server: the backend's environment variables), set
   `DISCORD_ENABLED=true` and `DISCORD_MODE=live`, and restart. Platform's
   log says how many announcements it read back.

Until then (`DISCORD_ENABLED` off, or `DISCORD_MODE=mock`), nothing leaves
the machine: announcements are kept in `backend/.data/discord-mock/`, and log
lines are printed.

Moving over: announcements made before this were in Platform's database. On
its first start with Discord on, Platform copies them into the channel,
keeping their ids, and takes them out of the database.

What Discord as the database costs, as with the orders app:

- **Anyone who can manage messages in the channel can delete an
  announcement.** Keep the channel's permissions tight.
- **Every start reads the whole announcements channel**, then again at most
  once a minute, so several servers stay in step.
- **If Discord can't be reached**, a new or changed announcement isn't saved
  and the admin is told to try again; nothing is half-saved. Log lines wait
  and are tried again (up to 5 times).
- **About 30 messages a minute per channel.** More wait their turn
  (`DISCORD_MAX_PER_MINUTE`).

For the screens to show an app's announcements, Platform must know the app:
**Platform → Applications**, with its key `crm`, `inventory`, `finance`,
`pharmacy`, `exec` (Admin) or `platform`, and the one app's `BACKEND_URL`
must point at the backend.

