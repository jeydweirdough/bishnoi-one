# Looking after the Bishnoi One repo

This page is for the repo owner. Everyone else only needs
[README.md](README.md).

---

## Adding people

Repo → **Settings → Collaborators → Add people**. They get an email
invitation, and can push once they accept it. Point them to the README.

---

## One-time GitHub setup for the actions

The repo has three actions, in `.github/workflows/`:

| Action | Runs when | What it does |
|---|---|---|
| **Sync branches** (`sync-branches.yml`) | any push to `main` or a `bishnoi-*` branch, every 30 minutes, or by hand | Merges each app branch's new work into `main`, then rebuilds every app branch from `main` and pushes it. It also creates the branch for a new app folder. |
| **Check apps** (`check-apps.yml`) | every pull request into `main` | Checks each `bishnoi-*` folder: name, `frontend/`, `backend/`, `.gitignore`, `README.md`, `GIT-GUIDE.md`, the workflow copy, and no secrets. |
| **Deploy <app>** (`deploy-<app>.yml`, one per app) | only by hand: **Run workflow** | Checks the app is set up, then deploys it to Vercel; stops and says what to do when it isn't ([below](#deployments-on-vercel-only-when-you-ask)). |

Set these once:

1. **Settings → Actions → General → Workflow permissions: Read and write.**
2. **Add a `SYNC_TOKEN` secret.** GitHub's own token isn't allowed to push
   workflow files, and each app branch carries a copy of the sync workflow.
   With this token, the sync can push those too, including a new app's
   branch.
   1. Create the token: your profile → **Settings → Developer settings →
      Personal access tokens → Fine-grained tokens → Generate new token**.
   2. Repository access: only `jeydweirdough/bishnoi`.
   3. Permissions: **Contents: Read and write**, **Workflows: Read and write**.
   4. Save it on the repo: **Settings → Secrets and variables → Actions →
      New repository secret**, named `SYNC_TOKEN`.
   5. The token expires on the date you chose. When it does, runs fail at
      checkout: make a new token and replace the secret.
3. **Optional: make the check required.** Settings → Branches → add a rule
   for `main` → "Require status checks to pass" → pick **check**. Then a
   pull request can't be merged while the check is red. If you require pull
   requests on `main`, also allow the `SYNC_TOKEN` owner to bypass the rule,
   or the sync can't push.

---

## Reviewing a new app

Someone proposes a new app as a pull request from an `add-app/<name>` branch
into `main` (README section 8). Before merging:

1. **Check apps is green.**
2. **The folder name is the branch name you want.** Once merged,
   `bishnoi-<name>` becomes the app's branch, and renaming it later means
   renaming the folder and deleting the old branch by hand. If you want a
   different name, ask them to rename the folder in the pull request.
3. **The ports are free:** no other app uses them (the screens port + 4000 =
   the API port).
4. **Nothing is committed that shouldn't be:** no `.env`, no `node_modules/`,
   no `.venv/`, no database files.
5. **It meets the benchmark** ([`benchmarks/`](benchmarks/README.md)): each
   feature it adds follows its row's decision in `benchmark-matrix.md` (an
   `open` row needs deciding first) and the rules in `patterns-to-adopt.md`,
   and its "Ours today" cells are filled in.

Then **merge** it. About a minute later, Sync branches creates the
`bishnoi-<name>` branch. Afterwards:

- Add the app to the layout, branch and port tables in `README.md`, and
  update the "next free ports" in README section 8.
- Tell the author its branch name, and delete the `add-app/<name>` branch
  (GitHub offers a button after the merge).

---

## Deployments on Vercel: only when you ask

Nothing deploys by itself. Vercel doesn't build from Git (every app's
`vercel.json`, screens and API: `git.deploymentEnabled: false`), and each app
has its own **Deploy** workflow that runs only when you press its button:
**Deploy Platform**, **Deploy CRM**, **Deploy Inventory**, **Deploy Pharmacy**,
**Deploy Finance**, **Deploy Executive Admin**, **Deploy In-Licensing**,
**Deploy Regulatory** (`.github/workflows/deploy-<app>.yml`; the steps they
share are in `deploy-app.yml`).

1. **Actions → Deploy <app> → Run workflow** (branch `main`).
2. Pick **screens and API**, **API only** or **screens only**, and whether to
   run the API's tests first (on by default).
3. **Run workflow.** It goes in this order, and stops at the first step that
   isn't right, before anything is deployed:
   1. **Is it set up?** The app's code can run on Vercel; `VERCEL_TOKEN`
      works; the app's Vercel projects exist with the right Root Directory;
      their **Production** environment variables are there (names only, never
      values: `.github/deploy.json` lists what each app needs); and the apps
      it depends on are online (the CRM and Inventory need the Platform's API
      first). The run's summary is a checklist: ✅ ready, ⚠️ optional and
      missing, ❌ blocking, with **What to do before deploying**, step by step.
   2. **Tests:** the API's tests, on GitHub's machines.
   3. **Deploy the API**, then **the screens**, each checked afterwards (the
      API's `/health`, the screens' sign-in page). An API that doesn't start
      says which setting to look at.
4. Blocked? Do the steps in the summary, then run it again.

Order the first time: **Platform** first, then the CRM and Inventory, then
the others. In-Licensing and Regulatory stop at the first check until their
code is ready for Vercel (the summary says what's missing).

- It deploys `main` as it is, to production. Commits get no Vercel checks,
  and the app branches get no preview builds.
- Each project's last deployed commit is the tag `deployed/<project>` (the
  repo's Tags show what's live). A bad deploy is put back from Vercel →
  the project → Deployments → **Instant Rollback**.
- Which folder goes to which project, and what each app needs:
  `.github/deploy.json`. When an app gets its Vercel projects, add them under
  `projects`; when its code is ready, set its `ready` to `true`.

Set up once:

1. Vercel → your avatar → **Account Settings → Tokens → Create**, on the
   account the Bishnoi One projects are in, with no expiry or a long one.
2. GitHub → the repo → **Settings → Secrets and variables → Actions → New
   repository secret**: `VERCEL_TOKEN`, the token.

The projects are on a personal account, so `scope` in `.github/deploy.json`
is empty (`""`): the action deploys to the token owner's own projects. If
they ever move into a Vercel team, set `scope` to the team's slug (the
`<slug>` in `vercel.com/<slug>/<project>`), or add a repository **variable**
`VERCEL_SCOPE` with it (same page, **Variables** tab; no commit needed).

If a deploy fails, the run's error says why: the token is wrong or expired
(make a new one), or it can't see the scope set (the error lists what it can
see).

If a whole app is being set up on Vercel for the first time: make its two
projects on Vercel (Root Directory `bishnoi-<app>/frontend` and
`bishnoi-<app>/backend`), add them to `deploy.json`, then tick it here.

---

## Putting an app online

Six apps are ready for Vercel: Platform, CRM, Inventory, Finance, Executive
Admin and Pharmacy. Each is two Vercel projects, its screens and its API, and
they call each other, so set them up in this order.

1. **Database logins.** On Supabase, run `scripts/supabase/app-users.sql`
   (SQL Editor). It gives each app its own login; copy each app's address
   from the result (the pooler, port 6543).
2. **Keys.** `node scripts/deploy-keys.mjs` prints every key the apps use to
   trust each other, beside the project and setting each goes in. Shown once.
3. **Projects.** On Vercel, make any project that doesn't exist yet, named as
   in `.github/deploy.json` (`bishnoi-<app>` for the screens, Root Directory
   `bishnoi-<app>/frontend`; `bishnoi-<app>-backend` for the API, Root Directory
   `bishnoi-<app>/backend`). The app's Deploy workflow stops with a message if one is
   missing.
4. **Settings**, below (each project → Settings → Environment Variables →
   Production).
5. **Deploy**: Actions → Deploy <app>, Platform first. Each deploys its API, then its screens.
6. **Platform > Applications:** set each app's address to its screens'
   address. A Bishnoi One account opens an app only at that address.
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
| `PLATFORM_PUBLIC_KEY` | From step 2 (not the Platform itself) |

**Only some APIs:**

| Project | Setting | Value |
|---|---|---|
| `bishnoi-platform-backend` | `PASS_SIGNING_KEY` | From step 2 (secret) |
| `bishnoi-inventory-backend` | `INTEGRATION_KEYS` | From step 2 |
| `bishnoi-finance-backend` | `INTEGRATION_KEYS` | From step 2 |
| `bishnoi-pharmacy-backend` | `INTEGRATION_KEYS` | From step 2 |
| `bishnoi-crm-backend` | `INVENTORY_API_URL` | `https://nabhi-inventory-backend.vercel.app` |
| | `INVENTORY_API_KEY` | From step 2 |
| | `INVENTORY_APP_URL` | `https://nabhi-inventory.vercel.app` |
| | `FINANCE_API_URL` | `https://nabhi-finance-backend.vercel.app` |
| | `FINANCE_API_KEY` | From step 2 |
| | `PHARMACY_API_URL` | `https://nabhi-pharmacy-backend.vercel.app` |
| | `PHARMACY_API_KEY` | From step 2 |
| | `ORDERS_API_URL`, `ORDERS_API_KEY` | From Bishnoi One Order, when it's ready |

**Every screens project** (`bishnoi-<app>`). The `NEXT_PUBLIC_` ones are built
in, so redeploy the screens after changing them:

| Setting | Value |
|---|---|
| `API_URL` | Its own API, e.g. `https://nabhi-crm-backend.vercel.app` |
| `PLATFORM_API_URL` | `https://nabhi-platform-backend.vercel.app` (announcements) |
| `NEXT_PUBLIC_BISHNOI_PLATFORM_URL` | `https://nabhi-platform.vercel.app` (the Bishnoi One account button; not on the Platform itself) |
| `NEXT_PUBLIC_BISHNOI_CRM_URL`, `_INVENTORY_URL`, `_FINANCE_URL`, `_EXEC_URL`, `_PHARMACY_URL` | Each app's screens, for links between the apps |

Leave `SHOW_DEMO_ACCOUNTS` unset online. The addresses above are the
defaults Vercel gives; use the real ones if a project has its own domain.

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
     `https://nabhi-inventory-backend.vercel.app` (no `/` at the end).
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
   `https://nabhi-finance-backend.vercel.app`, or `http://127.0.0.1:8303` on
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
   `https://nabhi-pharmacy-backend.vercel.app`, or `http://127.0.0.1:8307` on
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
3. Each app's API on Vercel: `PLATFORM_PUBLIC_KEY` = the public half (not
   secret; also shown at the platform API's `/pass/key`).
4. Each app's screens on Vercel: `NEXT_PUBLIC_BISHNOI_PLATFORM_URL` = the
   platform's address. The sign-in page then shows "Sign in with your Bishnoi One
   account".
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

For each app's screens to show announcements, Platform must know the app:
**Platform → Applications**, with its key `crm`, `inventory`, `finance`,
`pharmacy`, `exec` (Admin) or `platform`, and the screens' `PLATFORM_API_URL`
must point at Platform's API.

---

## When a sync fails

A red ✗ on **Actions → Sync branches** almost always means the same lines
were changed on `main` and on an app branch. Fix it from a full clone, in
**Git Bash**, with nothing uncommitted:

```
git switch main
git pull
bash scripts/sync-branches.sh     # stops at the conflict
git status                        # lists the files in conflict
# fix the <<<<<<< ======= >>>>>>> markers in each file
git add .
git commit                        # finishes the merge
bash scripts/sync-branches.sh     # run it again: it finishes and pushes
```

---

## Running the sync yourself

- **On GitHub:** Actions → Sync branches → **Run workflow**.
- **On your computer** (a full clone, on `main`, nothing uncommitted, in Git
  Bash):
  ```
  bash scripts/sync-branches.sh                 # every app
  bash scripts/sync-branches.sh bishnoi-crm       # just one app
  ```

---

## Changing the sync workflow

`.github/workflows/sync-branches.yml` has a copy in each app folder
(`bishnoi-*/.github/workflows/`). Each app branch needs its copy, because
GitHub only runs the workflows in the branch that was pushed. Keep all the
copies identical: Check apps fails a pull request if they differ.

After editing, copy it to every app, then stage them all:

```
for d in bishnoi-*/; do cp .github/workflows/sync-branches.yml "$d.github/workflows/"; done
git add .github "bishnoi-*/.github/*"
```

With `SYNC_TOKEN` set, pushing `main` is enough: the sync carries the copies
to the app branches. Without it, also run `bash scripts/sync-branches.sh`
once by hand.
