# Looking after the Bishnoi One repo

This page is for the repo owner. Everyone else only needs
[README.md](README.md).

---

## Adding people

Repo → **Settings → Collaborators → Add people**. They get an email
invitation, and can push once they accept it. Point them to the README.

---

## One-time GitHub setup for the actions

Everyone works on `main`. The per-app branches and the Sync branches action
were retired on 2026-10-24. The repo has one action, in `.github/workflows/`:

| Action | Runs when | What it does |
|---|---|---|
| **Check apps** (`check-apps.yml`) | every pull request into `main` | Checks each `bishnoi-*` folder: name, `backend/`, `.gitignore`, `README.md` and no `frontend/` (`bishnoi-one-app` excepted: it holds the screens, and needs `frontend/` and `README.md`), and no secrets. |

There is no Deploy workflow: the automated one was removed on 2026-10-22. Deployment is by hand now ([below](#deploying-by-hand)).

Set this once:

1. **Optional: make the check required.** Settings → Branches → add a rule
   for `main` → "Require status checks to pass" → pick **check**. Then a
   pull request can't be merged while the check is red.

---

## Reviewing a new app

Someone proposes a new app as a pull request from an `add-app/<name>` branch
into `main` (README section 8). Before merging:

1. **Check apps is green.**
2. **The folder name is the one you want.** Renaming it later means
   changing every place that names it. If you want a different name, ask
   them to rename the folder in the pull request.
3. **The API port is free:** no other app uses it. The app has no
   `frontend/`: its screens go in the one app, `bishnoi-one-app/frontend`,
   under a path of their own.
4. **Nothing is committed that shouldn't be:** no `.env`, no `node_modules/`,
   no `.venv/`, no database files.
5. **It meets the benchmark** ([`benchmarks/`](benchmarks/README.md)): each
   feature it adds follows its row's decision in `benchmark-matrix.md` (an
   `open` row needs deciding first) and the rules in `patterns-to-adopt.md`,
   and its "Ours today" cells are filled in.

Then **merge** it. Afterwards:

- Add the app to the layout and port tables in `README.md`, and
  update the "next free API port" in README section 8.
- Delete the `add-app/<name>` branch (GitHub offers a button after the
  merge).

---

## Deploying by hand

Nothing deploys by itself: pushing to `main` does not deploy anywhere. The
automated Deploy workflow was removed on 2026-10-22; deploy each app yourself
when you're ready, the **Platform first** (the CRM and Inventory need its API).

**Self-hosted (Coolify, the office server).** Each app is a resource in
Coolify, built from this repo. To release new code: open the resource and
press **Redeploy** (or **Deploy** after a fresh pull). Set each app's domain
under **Configuration → Domains**, its settings under **Environment
Variables**, and keep **Ports Exposes** matching the app's start port. The
screens are one more resource, the one app (`bishnoi-one-app/frontend`),
replacing the old per-app screens resources: deploy the APIs first, then the
one app. Watch the deployment log; an API that can't start
answers 503 and names the setting to check.

**Vercel (still possible, by hand).** Vercel doesn't build the APIs from Git
(every API's `vercel.json`: `git.deploymentEnabled: false`), so use the CLI:
`vercel --prod` in `bishnoi-<app>/backend` for each API, then in
`bishnoi-one-app/frontend` for the screens. Each Vercel project keeps its own Production
environment variables. A bad deploy is rolled back from the project →
Deployments → **Instant Rollback**.

Either way the order is the same: **Platform**, then the CRM and Inventory,
then the rest, then the one app's screens. In-Licensing and Regulatory show
"Coming soon" in the one app.

---

## Putting an app online

Six apps are ready for Vercel: Platform, CRM, Inventory, Finance, Executive
Admin and Pharmacy. Each is one Vercel project for its API, and one more
project holds every app's screens (the one app). They call each other, so set
them up in this order.

1. **Database logins.** On Supabase, run `scripts/supabase/app-users.sql`
   (SQL Editor). It gives each app its own login; copy each app's address
   from the result (the pooler, port 6543).
2. **Key.** `node scripts/deploy-keys.mjs` prints the Platform's signing key
   (`PASS_SIGNING_KEY`), the one key made by hand. Shown once. Every other key
   comes from the Platform's Connections page (step 6).
3. **Projects.** On Vercel, make any project that doesn't exist yet:
   `bishnoi-<app>-backend` for each API (Root Directory
   `bishnoi-<app>/backend`), and one project for the screens (Root Directory
   `bishnoi-one-app/frontend`). The old per-app screens projects are replaced
   by it.
4. **Settings**, below (each project → Settings → Environment Variables →
   Production).
5. **Deploy** each app by hand (see [Deploying by hand](#deploying-by-hand)
   above), the Platform first; the APIs, then the one app.
6. **Platform > Applications:** set each app's API address. The one app's
   address is the Platform's `ONE_APP_URL` (the same as the one app's own
   `ONE_APP_URL`; see [bishnoi-one-app/README.md](bishnoi-one-app/README.md)).
   Then **Platform > Connections:** switch on the links between the apps. Each
   app's connect key is sent to its registered API address, signed, when it
   first asks: nothing to copy onto Vercel.
   A company's outside services (Zoho Books, Gmail, Outlook, Zoho Mail) are
   filled in on the Platform too: **Companies > the company > Connections**.
7. **First sign-in:** sign in with the FIRST_ADMIN account, then delete
   `FIRST_ADMIN_PASSWORD` from the project and redeploy.
8. **Check:** each API's `/health` answers `{"ok": true}`. If a setting is
   wrong, every request answers 503 naming the setting to look at.

**Every API** (`bishnoi-<app>-backend`):

| Setting | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Its login from step 1 |
| `ALLOWED_HOSTS` | `["bishnoi-<app>-backend.vercel.app"]`, its own address |
| `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD` | The first administrator (step 7) |
| `PLATFORM_API_URL` | `https://bishnoi-one-platform-backend.vercel.app` (not the Platform itself): its public key is fetched from there |

**Only some APIs:**

| Project | Setting | Value |
|---|---|---|
| `bishnoi-platform-backend` | `PASS_SIGNING_KEY` | From step 2 (secret) |
| `bishnoi-crm-backend` | `CRM_APP_URL` | `https://bishnoi-one-crm.vercel.app` (links in emails) |
| | `ORDERS_API_URL`, `ORDERS_API_KEY` | From Bishnoi One Order, when it's ready |

**The screens project** (the one app, `bishnoi-one-app/frontend`):

| Setting | Value |
|---|---|
| `ONE_APP_URL` | Its own address, e.g. `https://one.bishnoi.ai` (the same as the Platform's `ONE_APP_URL`) |
| `PLATFORM_API_URL` | The Platform's API, e.g. `https://bishnoi-one-platform-backend.vercel.app` |
| `CRM_API_URL`, `INVENTORY_API_URL`, `FINANCE_API_URL`, `ADMIN_API_URL`, `PHARMACY_API_URL` | Each module's API, e.g. `https://bishnoi-one-crm-backend.vercel.app` |
| `INLICENSING_API_URL`, `REGULATORY_API_URL` | Optional for now: those modules show "Coming soon" |

Every setting is explained in `bishnoi-one-app/frontend/.env.example` and
[bishnoi-one-app/README.md](bishnoi-one-app/README.md).

What was checked before these were called ready (September 28, 2026): each
app's tests, its production build, its migrations on a Supabase-like Postgres
under its own login, a browser through every page, and all six running
together: the CRM's products and stock from Inventory, tax and marketing requests
through Finance, Raise order to a stand-in Bishnoi One Order, and one Bishnoi One account
opening all five apps.

---

## Linking the CRM to Inventory

The CRM's products come from Inventory, with their SRP, and it shows
Inventory's stock on Products and on new quotes. The two APIs talk through a
shared key. Set up once, on Vercel (each project → **Settings → Environment
Variables**, then redeploy it):

1. Make a key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. **bishnoi-inventory-backend:** `INTEGRATION_KEYS` = `["crm:<the key>"]`.
3. **bishnoi-crm-backend:**
   - `INVENTORY_API_URL` = the Inventory API's address, e.g.
     `https://bishnoi-one-inventory-backend.vercel.app` (no `/` at the end).
   - `INVENTORY_API_KEY` = the key.
   - `INVENTORY_APP_URL` = Inventory's screens, for the "Add it in Inventory"
     button (optional).

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

Finance works out the tax on CRM quotes (the Philippines: VAT, exempt,
zero-rated, senior citizen and PWD), as the last step of the CRM's price
rules.

1. Make a key, as above (or use `scripts/deploy-keys.mjs`). Use a different
   one from the Inventory link.
2. **Finance API** (`bishnoi-finance-backend`, or `bishnoi-finance/backend/.env`):
   `INTEGRATION_KEYS` = `["crm:<the key>"]`.
3. **CRM API** (`bishnoi-crm-backend`, or `bishnoi-crm/backend/.env`):
   `FINANCE_API_URL` = Finance's API address (e.g.
   `https://bishnoi-one-finance-backend.vercel.app`, or `http://127.0.0.1:8303` on
   one computer) and `FINANCE_API_KEY` = the key.
4. Restart both. In Finance, an admin fills in **Tax → Registration** (VAT
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

Pharmacy checks that orders are compliant. A CRM quote marked **Rx** can't be
ordered until a pharmacist in Pharmacy verifies its prescription.

1. Make a key, as above. Use a different one from the other links.
2. **Pharmacy API** (`bishnoi-pharmacy-backend`, or `bishnoi-pharmacy/backend/.env`):
   `INTEGRATION_KEYS` = `["crm:<the key>"]`.
3. **CRM API** (`bishnoi-crm-backend`, or `bishnoi-crm/backend/.env`):
   `PHARMACY_API_URL` = Pharmacy's API address (e.g.
   `https://bishnoi-one-pharmacy-backend.vercel.app`, or `http://127.0.0.1:8307` on
   one computer) and `PHARMACY_API_KEY` = the key.
4. Restart both.

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
`bishnoi-pharmacy/backend/app/routers/integration.py`. Give each app its own
entry in `INTEGRATION_KEYS`, e.g. `["crm:<key>", "orders:<key>"]`.

---

## Linking the CRM to Bishnoi One Order

Bishnoi One Order is its own application. On a quote, **Raise order** sends the quote
to it; the CRM keeps the order number it answers with, so a quote is ordered
once. The button is off until the quote is approved and its guarantee letter is
checked.

On the CRM API (`bishnoi-crm/backend`, and Vercel):

| Variable | Value |
|---|---|
| `ORDERS_API_URL` | Bishnoi One Order's API, e.g. `https://orders-api.example.com` |
| `ORDERS_API_KEY` | The key Bishnoi One Order gave the CRM |

The CRM calls `POST {ORDERS_API_URL}/orders` with the headers `X-Bishnoi-Key`
and `Idempotency-Key` (the quote's id, the same on a retry), and expects
`{"id", "number"}` back, with an optional `"url"` for the "Order SO-..." link.
The payload is described at the top of `bishnoi-crm/backend/app/orders.py`; to
see it for a real quote, call `GET /quotes/{id}/order-payload` on the CRM API.

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

1. Make the platform's key pair once: in `bishnoi-platform/backend`,
   `uv run python -m app.passes`. It prints both halves.
2. Platform API on Vercel: `PASS_SIGNING_KEY` = the private half (secret).
3. Each app's API on Vercel: `PLATFORM_API_URL` = the platform's API. The app
   fetches the public half from its `/pass/key`, and again when the key is
   replaced; `PLATFORM_PUBLIC_KEY` is only for pinning it.
4. The screens are the one app: one Bishnoi One sign-in there opens every
   module, and roles are managed centrally in `/platform/access`. Its
   `PLATFORM_API_URL` = the platform's API (see
   [bishnoi-one-app/README.md](bishnoi-one-app/README.md)).
5. Platform > Applications: each application's address must be its real
   address: the pass goes back only to `<that address>/auth/platform` (or to
   Bishnoi One.exe on the same PC).
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
   `DISCORD_ANNOUNCEMENTS_WEBHOOK_URL`; the logs one in every app's
   `DISCORD_LOGS_WEBHOOK_URL`. Don't use one channel for both.
3. In the [Discord Developer Portal](https://discord.com/developers/applications),
   **New Application** → **Bot** → **Reset Token**: that's
   `DISCORD_BOT_TOKEN`, the same in every app. On the same page, turn on
   **Message Content Intent** and save; without it Discord gives the
   messages back blank.
4. **OAuth2 → URL Generator**: tick `bot`, then **View Channels**, **Read
   Message History**, **Create Public Threads** and **Send Messages in
   Threads**. Open the URL and add the bot to the server, with access to both
   channels.
5. In each app's `backend/.env` (on Vercel: its environment variables), set
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
  once a minute, so several servers (Vercel) stay in step.
- **If Discord can't be reached**, a new or changed announcement isn't saved
  and the admin is told to try again; nothing is half-saved. Log lines wait
  and are tried again (up to 5 times); on Vercel they may go out with the
  next request.
- **About 30 messages a minute per channel.** More wait their turn
  (`DISCORD_MAX_PER_MINUTE`).

For the screens to show an app's announcements, Platform must know the app:
**Platform → Applications**, with its key `crm`, `inventory`, `finance`,
`pharmacy`, `exec` (Admin) or `platform`, and the one app's `PLATFORM_API_URL`
must point at Platform's API.

