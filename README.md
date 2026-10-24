# Bishnoi One

Bishnoi One is a set of separate business apps (Admin, CRM, Finance, Inventory,
and more) kept in one GitHub repo. Each app has its own API; every app's
screens are in one web app, with one sign-in. This page shows you how to:

- get the code onto your computer
- keep it up to date
- share your changes
- run an app
- add a new app

Repo: **https://github.com/jeydweirdough/nabhi**

Everyday Git is three commands: **clone** once, then **pull** and **push**.
The rest of this page walks through them.

---

## Contents

1. [How the repo is laid out](#1-how-the-repo-is-laid-out)
2. [Before you start (once per computer)](#2-before-you-start-once-per-computer)
3. [Clone: download the code](#3-clone-download-the-code)
4. [Pull and push: everyday work](#4-pull-and-push-everyday-work)
5. [Run an app](#5-run-an-app)
6. [Settings (`.env`) for every app](#6-settings-env-for-every-app)
7. [Benchmarks: what we build to](#7-benchmarks-what-we-build-to)
8. [Add a new app](#8-add-a-new-app)
9. [What happens after you push](#9-what-happens-after-you-push)
10. [Rules](#10-rules)
11. [Cheat sheet](#11-cheat-sheet)

---

## 1. How the repo is laid out

Each app's API lives in its own folder, in **`backend/`** (Python, FastAPI).
The APIs don't depend on each other. Each one has its own settings and
database.

Every app's screens are in **one** Next.js app, `bishnoi-one-app/frontend`,
with each module under its own path. One Bishnoi One sign-in (a Platform
account) opens every module. See
[bishnoi-one-app/README.md](bishnoi-one-app/README.md).

```
bishnoi/
├── bishnoi-one-app/        screens :4301   (every module, one sign-in)
├── bishnoi-admin/          API :8300
├── bishnoi-crm/            API :8302
├── bishnoi-finance/        API :8303
├── bishnoi-inventory/      API :8304
├── bishnoi-platform/       API :8305
├── bishnoi-in-licensing/   API :8306
├── bishnoi-pharmacy/       API :8307
└── bishnoi-regulatory/     API :8308
```

| Module | Path in the one app |
|---|---|
| CRM | `/crm` |
| Inventory | `/inventory` |
| Finance | `/finance` |
| Executive Admin | `/admin` |
| Pharmacy | `/pharmacy` |
| Platform: company administrators (people, roles, modules) | `/platform/access` |
| Platform: Bishnoi One staff console (own staff sign-in) | `/platform/console` |
| In-Licensing, Regulatory | `/in-licensing`, `/regulatory` ("Coming soon") |

### Work on `main`

Every app and the one app are in one repo. Everyone works on `main`: clone
the whole repo, pull, and push. Want a branch for a change? Branch from
`main`, but never name it `bishnoi-…`.

---

## 2. Before you start (once per computer)

### Step 1: Get access

Ask the repo owner to add you to the repo. GitHub sends you an email
invitation. **Accept it**, or you won't be able to push.

### Step 2: Install the tools

| Tool | What it's for | Get it |
|---|---|---|
| Git | clone, pull, push | https://git-scm.com |
| Node.js (LTS) | running the screens | https://nodejs.org |
| uv | running the Python API | https://docs.astral.sh/uv/ |

### Step 3: Tell Git who you are

Open a terminal (PowerShell, Git Bash or Terminal) and run:

```
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

Every commit carries this name, and GitHub shows it next to your work. Use the
same email as your GitHub account, so the commits are linked to your profile.

### Step 4: Sign in to GitHub

You don't have to do anything now. The first time you push, Git opens a
browser window: sign in to GitHub, and Git remembers you from then on.

> **Shared office machine?** Use `git use-jeyd` or `git use-backend` to
> switch accounts, and `git who` to check which one is active, before you
> commit.

---

## 3. Clone: download the code

Do this once. In your terminal, go to the folder where you keep your
projects, then clone the whole repo:

```
git clone https://github.com/jeydweirdough/nabhi.git bishnoi
cd bishnoi
```

You get `main`, with every app and the one app, each in its own folder.

### Then: create your settings files

Passwords and other secrets are never stored in Git. Each app includes
example files instead. `npm run <app>` copies them for you
([section 5](#5-run-an-app)); to do it by hand, copy them once per app:

| Copy this… | …to this |
|---|---|
| `backend/.env.example` | `backend/.env` (in each app's folder) |
| `bishnoi-one-app/frontend/.env.example` | `bishnoi-one-app/frontend/.env.local` (the screens) |

What each setting means, and a complete file for every app, is in
[section 6](#6-settings-env-for-every-app). You're ready. See [Run an app](#5-run-an-app).

---

## 4. Pull and push: everyday work

Every time you work, follow the same loop:

```
pull  →  make your changes  →  commit  →  pull  →  push
```

### 1. Pull before you start

```
git pull
```

This downloads everything others pushed since your last pull.

### 2. Make your changes

Edit the code as usual. To check what you've changed at any time:

```
git status      # which files changed
git diff        # the exact lines that changed
```

### 3. Commit: save your changes

```
git add .
git commit -m "Add expiry column to stock list"
```

Describe *what changed*: "Fix total on the invoice page" helps everyone;
"update" or "fix" doesn't.

You can commit as often as you like. Commits stay on your computer until you
push.

### 4. Pull again, then push: share your changes

```
git pull
git push
```

That's it. Your work is on GitHub, on `main`
(see [section 9](#9-what-happens-after-you-push)).

### If `git push` is rejected

Someone pushed while you were working. Bring in their work, then push:

```
git pull --rebase
git push
```

### If Git says there's a conflict

You and someone else changed the same lines. Git lists the files. Open each
one and look for these markers:

```
<<<<<<< yours
your version
=======
their version
>>>>>>> theirs
```

Edit each one down to the correct final code and delete the three marker
lines. Then:

```
git add .
git rebase --continue
git push
```

Stuck? `git rebase --abort` puts everything back the way it was before you
pulled, and you can ask for help.

---

## 5. Run an app

### The quick way

From the top of the repo, one command runs the Platform, CRM, Inventory,
Finance, Admin and Pharmacy APIs together with the one app's screens:

```
npm run one
```

Then open **http://localhost:4301** and sign in with your Bishnoi One
account. **Ctrl+C** stops everything. `npm run one -- --setup` gets it all
ready and starts nothing.

The first time, it gets each part ready by itself: it copies the `.env`
example files, makes each API's Python environment (`backend/.venv`, with
`uv sync`) and installs the screens' packages (`npm install`). After that it
only redoes what changed.

To run one API alone, use its name. These run the API only: the screens are
all in the one app.

```
npm run bishnoi-crm
```

Every app has one: `npm run bishnoi-admin`, `bishnoi-crm`, `bishnoi-finance`,
`bishnoi-inventory`, `bishnoi-pharmacy`, `bishnoi-platform`, `bishnoi-in-licensing`
and `bishnoi-regulatory`.

| Also | Does |
|---|---|
| `npm run bishnoi-one-app` | The one app's screens only |
| `npm run bishnoi-crm -- --setup` | Gets that API ready, starts nothing |
| `npm run setup` | Gets **every** app ready |

It needs only Node.js and uv (step 2): the root `package.json` has no
packages of its own to install.

### As a desktop app

To try the one app the way it will be used on a PC, in a window of its own:

```
npm run bishnoi-one-app:app
```

The first time, it installs what the window needs (in `desktop/`). The APIs
it uses must be running (for example with `npm run one` in another terminal,
or each API on its own). The per-app `:app` commands are gone: every module
opens in this one window. See [bishnoi-one-app/README.md](bishnoi-one-app/README.md).

This is for trying the app on your own computer. Installers for other PCs
come later.

### By hand

Every API runs the same way. First go into the app's folder
(`cd bishnoi-crm`).

```
cd backend
uv sync
uv run main.py
```

The screens are the one app, in `bishnoi-one-app/frontend`; how to
run it by hand is in [bishnoi-one-app/README.md](bishnoi-one-app/README.md).
Each module is at its path on http://localhost:4301
([section 1](#1-how-the-repo-is-laid-out)).

| App | API |
|---|---|
| Admin | http://127.0.0.1:8300 |
| CRM | http://127.0.0.1:8302 |
| Finance | http://127.0.0.1:8303 |
| Inventory | http://127.0.0.1:8304 |
| Platform | http://127.0.0.1:8305 |
| In-Licensing | http://127.0.0.1:8306 |
| Pharmacy | http://127.0.0.1:8307 |
| Regulatory | http://127.0.0.1:8308 |

### Your first account

One Bishnoi One sign-in (a Platform account) opens every module in the one
app, and roles are managed centrally in `/platform/access`. There's no
sign-up page. Accounts are made with the users tool, run from an app's
`backend/` folder (for your Bishnoi One account, `bishnoi-platform/backend`):

```
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
```

Later, `list`, `password`, `disable` and `enable` manage accounts.

### Good to know

- The database is set by `DATABASE_URL` in `backend/.env`. By default it's a
  local SQLite file in `backend/.data/`. Every setting is in
  [section 6](#6-settings-env-for-every-app).
- Every API has interactive docs at `/docs`
  (e.g. http://127.0.0.1:8302/docs).
- Run an API's tests with `uv run pytest` in its `backend/` folder.
- On Windows, if the screens stop with
  `listen EACCES: permission denied 0.0.0.0:4301`, Windows has set that port
  aside (Hyper-V, WSL and Docker do this, and it changes from one restart to
  the next). `netsh interface ipv4 show excludedportrange protocol=tcp` shows
  which ports. To keep it away from the Bishnoi One ports for good, run this once
  in a terminal opened as administrator, then restart the PC:

  ```
  netsh int ipv4 set dynamicport tcp start=49152 num=16384
  netsh int ipv6 set dynamicport tcp start=49152 num=16384
  ```

### Put an app online (Vercel)

Each app is **one Vercel project** from this repo, for its API, plus **one
project for the one app's screens** (every module). When you import the repo,
set the project's **Root Directory** to the app's `backend/` folder, or to
`bishnoi-one-app/frontend` for the screens.

Ready for Vercel today: **CRM, Inventory, Pharmacy, Platform**. Admin,
Finance, In-Licensing and Regulatory don't have the Postgres driver, the
Vercel entry point (`app/server.py`) or the first-admin settings yet, so they
run on your computer only.

In each project: **Settings → Environment Variables**. Paste a block like the
ones below into the first field, and Vercel splits it into one variable per
line.

**Every API project:**

```
DATABASE_URL=postgresql://postgres.<project>:<password>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
ENVIRONMENT=production
ALLOWED_HOSTS=["<this API's address>.vercel.app"]
FIRST_ADMIN_EMAIL=you@yourcompany.com
FIRST_ADMIN_NAME=Your Name
FIRST_ADMIN_PASSWORD=<at least 8 characters>
```

- `DATABASE_URL`: on Supabase, the **Transaction pooler** address (Connect →
  Transaction pooler, port 6543). The direct `db.<project>.supabase.co`
  address doesn't work from Vercel. In the password, write `#` as `%23`, `@`
  as `%40` and `/` as `%2F`. Don't put quotes around it.
- The apps can share one database: every app's tables start with its own
  prefix (`nbcm_`, `nbin_`, `nbph_`, `nbpl_`…), so they never collide.
- `ALLOWED_HOSTS`: the API's own address, as JSON. A request to any other
  address is refused.
- `FIRST_ADMIN_*`: makes the first administrator on start, but only when that
  app has no accounts yet; after that it's ignored. Remove
  `FIRST_ADMIN_PASSWORD` once you've signed in, and add everyone else from
  the app itself.

**The CRM and Inventory on Neon** (decided 2026-10-05; Supabase works the same way):

1. At neon.com (free, no card), make **one project per app**: `bishnoi-crm` and
   `bishnoi-inventory`, region **Singapore** (closest to the Philippines). Set
   the compute to **0.25 CU, autoscaling up to 0.5 CU**: the free plan's 100
   compute-hours a month then cover office hours. Each project gets its own
   1 GB and hours, and the two apps only talk through their APIs anyway.
2. In each project: **Connect**, pooled connection (the address with
   `-pooler`), and copy it. That's the API project's `DATABASE_URL` on Vercel.
3. Copy this computer's data into it, once, from the app's `backend/` folder:
   `uv run python -m app.tools.copy_database --to "<the pooled address>"`.
   It makes the tables, copies every row, and checks every table matches. A
   database that already has people in it is refused unless `--replace`.
   `--setup` copies only the setup (people, roles, teams, settings, products,
   prices, KPIs, taxes, warehouses, stock) and leaves customers, deals,
   quotes, activities, visits, orders, invoices, the audit log and sign-ins
   behind (CRM, Inventory and Finance).
4. Backups: put the same address in the app's `backend/.env` as `BACKUP_FROM`
   (this computer keeps its own SQLite file for trying things), and run
   `scripts/backup-online-databases.cmd` by hand or nightly with Task
   Scheduler (the command is in the file). The last 30 days stay in
   `backend/.data/backups/`.

**Several companies, one CRM (and one Inventory)** (since 2026-10-05). Each
company has a database of its own, beside `DATABASE_URL` with the company's
short name added: `neondb` → `neondb_getmeds`, `neondb_northwind`; on this
computer `crm.db` → `crm-getmeds.db`. So `DATABASE_URL` on Vercel stays the
**base** address (`…/neondb`): the app makes each company's database the first
time that company signs in, once the company is registered on Bishnoi One
Platform and given the app. Which company a request is for comes from the
sign-in (the session's token starts with it). The tools take
`--company getmeds` (default on this computer: `DEFAULT_COMPANY`), and the
backup copies every company, one file each. Someone who works for two
companies has a Platform account row at each, under one email and one
password, and uses **Switch company** in the app's menu.

**The screens project (the one app):**

```
ONE_APP_URL=https://one.bishnoi.ai
PLATFORM_API_URL=https://<the Platform's API address>
CRM_API_URL=https://<the CRM's API address>
INVENTORY_API_URL=https://<Inventory's API address>
FINANCE_API_URL=https://<Finance's API address>
ADMIN_API_URL=https://<Admin's API address>
PHARMACY_API_URL=https://<Pharmacy's API address>
```

- `ONE_APP_URL` must match the Platform's `ONE_APP_URL`.
- `INLICENSING_API_URL` and `REGULATORY_API_URL` are there too, for when
  those modules have screens.
- Every setting is explained in `bishnoi-one-app/frontend/.env.example` and
  [bishnoi-one-app/README.md](bishnoi-one-app/README.md).

**Linked apps:** the CRM's API also needs `INVENTORY_API_URL`/`KEY` and
`FINANCE_API_URL`/`KEY` for the apps it uses, and each of those APIs needs
the matching `INTEGRATION_KEYS` ([Linking apps](#linking-apps)).

| Project | Root directory |
|---|---|
| CRM API | `bishnoi-crm/backend` |
| Inventory API | `bishnoi-inventory/backend` |
| Pharmacy API | `bishnoi-pharmacy/backend` |
| Platform API | `bishnoi-platform/backend` |
| The one app (every module's screens) | `bishnoi-one-app/frontend` |

Use the addresses Vercel actually gives your projects (e.g.
`bishnoi-one-inventory-backend.vercel.app`): the API's `ALLOWED_HOSTS` and the
one app's matching `<APP>_API_URL` must both name it.

**Pushing doesn't deploy.** To put an app online, deploy it by hand, the
Platform first: on the office Coolify server press **Redeploy**, or run
`vercel --prod` in the app's `backend` folder; then deploy the one app from
`bishnoi-one-app/frontend` (MAINTAINING.md, "Deploying by hand").

If an API can't start, every request to it answers `503` with what's wrong
and which setting to check (`"problem": "database"` → `DATABASE_URL`). The
full error is in the project's logs.

---

## 6. Settings (`.env`) for every app

Each app's API reads its settings from one file, and the one app's screens
from another. Git never stores them:

| File | Read by | Starts from |
|---|---|---|
| `bishnoi-<app>/backend/.env` | that app's API | `backend/.env.example` |
| `bishnoi-one-app/frontend/.env.local` | the screens (every module) | `bishnoi-one-app/frontend/.env.example` |

On your computer, **every setting has a default that works**, so the
copied example files are enough to run an app. Change a setting only when
you need what it does. Online (Vercel), set the same names under
**Settings → Environment Variables**
([Put an app online](#put-an-app-online-vercel)).

Lists are written as JSON: `["a", "b"]`. Restart the API (or `npm run dev`)
after you change a file.

### Backend settings every app has

| Setting | Default | What it does |
|---|---|---|
| `ENVIRONMENT` | `development` | Set `production` online. Production hides the API docs (`/docs`) and turns off demo accounts. |
| `DATABASE_URL` | `sqlite:///.data/<app>.db` | The app's database. A local SQLite file by default; a `postgresql://…` address for Postgres (Supabase, Neon). Apps may share one database: each app's tables have its own prefix ([below](#table-prefixes)). |
| `SESSION_HOURS` | `10` | How long a sign-in lasts. |
| `LOGIN_ATTEMPTS` | `5` | Wrong passwords in a row before an account is locked for a while. |
| `LOGIN_LOCKOUT_MINUTES` | `15` | How long that lock lasts. |
| `ORG_NAME` | `Bishnoi One` | The company name the screens show. |
| `ORG_CURRENCY` | `PHP` | The currency amounts are shown in. |
| `ORG_MINOR_UNITS` | `2` | Decimal places of that currency (centavos). |
| `ORG_LOCALE` | `en-PH` | How numbers and dates are written. |
| `ORG_TIMEZONE` | `Asia/Manila` | The company's time zone: what counts as "today". |
| `ALLOWED_HOSTS` | `["localhost", "127.0.0.1"]` | Addresses the API answers to. Online: its own Vercel address. |
| `CORS_ORIGINS` | `[]` | Browser addresses allowed to call the API directly. Leave it empty: the screens' server calls the API, not the browser. |
| `DISCORD_ENABLED` | `false` | `true` sends this app's log to Discord (and, in Platform, keeps announcements there). See MAINTAINING.md, "Connecting Discord". |
| `DISCORD_MODE` | `mock` | `live` really posts; `mock` keeps everything on this machine. |
| `DISCORD_BOT_TOKEN` | not set | The Discord bot: reads the channels back and starts the threads. The same in every app. |
| `DISCORD_LOGS_WEBHOOK_URL` | not set | A webhook in the logs channel. This app's log goes there, a thread a day (`LOG-CRM-20260926`). |
| `DISCORD_MAX_PER_MINUTE` | `30` | Most Discord messages a minute; more wait their turn. |

### Backend settings only some apps have

| App | Setting | Default | What it does |
|---|---|---|---|
| CRM, Inventory, Pharmacy, Platform | `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD` | not set | Makes the first administrator on start, **only** while the app has no accounts. For hosts where you can't run the users tool (Vercel). Remove the password after you've signed in. |
| CRM, Inventory | `PLATFORM_API_URL` | not set | Bishnoi One Platform's API, where the app checks that a company is registered, active and given the app; its public key, for passes, is fetched from there too. Not set: on this computer the companies in `DEV_COMPANIES` are allowed; in production, none. |
| CRM, Inventory | `FIRST_ADMIN_COMPANY` | not set | The one company whose database gets the `FIRST_ADMIN_*` account (each company has its own database). Not set: `DEFAULT_COMPANY` on this computer, none in production, where a company's administrators sign in with their Bishnoi One account. |
| CRM, Inventory | `DEFAULT_COMPANY`, `DEV_COMPANIES` | `getmeds`, `["getmeds","northwind"]` | This computer only: the company a request is for when it doesn't say, and the companies allowed without the Platform. Ignored in production. |
| Inventory, Pharmacy | `EXPIRY_WARNING_DAYS` | `90` | A batch expiring within this many days is flagged "expiring soon". |
| Inventory | `DEAD_STOCK_DAYS` | `180` | Stock with nothing issued or moved out for this long counts as dead stock. |
| Pharmacy | `PRESCRIPTION_VALID_DAYS` | `180` | A prescription older than this can't be verified. |
| CRM | `INVENTORY_API_URL`, `INVENTORY_API_KEY` | not set | Links the CRM to Inventory: the product list and stock levels come from there. Not set: products are added and priced in the CRM by hand. |
| CRM | `INVENTORY_APP_URL` | not set | Inventory's screens, for the "Add it in Inventory" link on Products. |
| CRM | `FINANCE_API_URL`, `FINANCE_API_KEY` | not set | Links the CRM to Finance, which works out tax as the last step of the price rules. Not set: quotes are priced without tax. |
| CRM | `PHARMACY_API_URL`, `PHARMACY_API_KEY` | not set | Links the CRM to Pharmacy, where a pharmacist checks quotes marked Rx before they're ordered. Not set: an Rx quote can't be sent for checking, so it can't be ordered. |
| Inventory, Finance, Pharmacy | `INTEGRATION_KEYS` | `[]` | Which other apps may call this one, as `name:key` pairs. See [Linking apps](#linking-apps). |
| Platform | `DISCORD_ANNOUNCEMENTS_WEBHOOK_URL` | not set | A webhook in the announcements channel, where announcements are kept, a thread each (`ANN-20260926-0001`). |

### Linking apps

Some apps ask others for data: the CRM asks **Inventory** for products and
stock, **Finance** for tax, and **Pharmacy** to check quotes marked Rx; **Finance** asks the
**CRM** for customers to invoice (`CRM_API_URL`, `CRM_API_KEY` in Finance, and
`INTEGRATION_KEYS=["finance:<the key>"]` in the CRM), and **Inventory** for the suppliers its
bills are made out to (`INVENTORY_API_URL`, `INVENTORY_API_KEY` in Finance; the Platform links
Finance to Inventory by itself, once). Finance also names its company to Inventory, which keeps a
database per company: `COMPANY=getmeds` in Finance (unset, the company of the latest sign-in).
The app being asked lists a key for each caller, and the caller sends that key with every request.

1. Make a key (at least 24 characters):

   ```
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. In the app **being asked**, list it under the caller's name:

   ```
   INTEGRATION_KEYS=["crm:<the key>"]
   ```

3. In the **caller**, set the other app's API address and the same key:

   ```
   FINANCE_API_URL=http://127.0.0.1:8303
   FINANCE_API_KEY=<the key>
   ```

Use a different key for each link: one for CRM → Inventory, another for
CRM → Finance, another for CRM → Pharmacy. Restart both APIs. If the key is missing or doesn't match,
the CRM tells its users the other app can't be reached; nothing breaks.

### Screens settings (the one app)

The screens are one app, so they have one settings file:
`bishnoi-one-app/frontend/.env.local`. Only the one app's server talks to the
APIs; browsers never do.

| Setting | Default | What it does |
|---|---|---|
| `ONE_APP_URL` | `http://localhost:4301` | The one app's own address, as the Platform knows it (online, `https://one.bishnoi.ai`; the Platform's `ONE_APP_URL` must be the same). |
| `PLATFORM_API_URL` | `http://127.0.0.1:8305` | Bishnoi One Platform's API: the one sign-in, and the Platform module's API. |
| `CRM_API_URL`, `INVENTORY_API_URL`, `FINANCE_API_URL`, `ADMIN_API_URL`, `PHARMACY_API_URL`, `INLICENSING_API_URL`, `REGULATORY_API_URL` | each module's API on your computer (`http://127.0.0.1:83xx`) | Where the screens find each module's API. |

The full list is in `bishnoi-one-app/frontend/.env.example`, and
[bishnoi-one-app/README.md](bishnoi-one-app/README.md) explains it.

### Complete files, app by app

Ready to copy for your computer. Lines starting with `#` are optional:
remove the `#` to use one.

The screens' file, `bishnoi-one-app/frontend/.env.local`, is a copy of
`bishnoi-one-app/frontend/.env.example`: every line in it is optional on your
computer ([Screens settings](#screens-settings-the-one-app)).

<details>
<summary><b>Admin</b> (API :8300)</summary>

`bishnoi-admin/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/admin.db
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Bishnoi One
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]
```

</details>

<details>
<summary><b>CRM</b> (API :8302)</summary>

`bishnoi-crm/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/crm.db
# FIRST_ADMIN_EMAIL=you@example.com
# FIRST_ADMIN_NAME=Your Name
# FIRST_ADMIN_PASSWORD=
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Bishnoi One
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]

# Products and stock from Inventory (the key is "crm:<key>" in Inventory's INTEGRATION_KEYS)
# INVENTORY_API_URL=http://127.0.0.1:8304
# INVENTORY_API_KEY=
# INVENTORY_APP_URL=http://localhost:4304

# Tax from Finance (the key is "crm:<key>" in Finance's INTEGRATION_KEYS)
# FINANCE_API_URL=http://127.0.0.1:8303
# FINANCE_API_KEY=

# The pharmacist's check on Rx quotes (the key is "crm:<key>" in Pharmacy's INTEGRATION_KEYS)
# PHARMACY_API_URL=http://127.0.0.1:8307
# PHARMACY_API_KEY=
```

</details>

<details>
<summary><b>Finance</b> (API :8303)</summary>

`bishnoi-finance/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/finance.db
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Bishnoi One
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]

# Apps allowed to ask Finance for tax
# INTEGRATION_KEYS=["crm:<the CRM's FINANCE_API_KEY>"]
```

</details>

<details>
<summary><b>Inventory</b> (API :8304)</summary>

`bishnoi-inventory/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/inventory.db
# FIRST_ADMIN_EMAIL=you@example.com
# FIRST_ADMIN_NAME=Your Name
# FIRST_ADMIN_PASSWORD=
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# EXPIRY_WARNING_DAYS=90
# DEAD_STOCK_DAYS=180
# ORG_NAME=Bishnoi One
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]

# Apps allowed to read products and stock
# INTEGRATION_KEYS=["crm:<the CRM's INVENTORY_API_KEY>"]
```

</details>

<details>
<summary><b>Platform</b> (API :8305)</summary>

`bishnoi-platform/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/platform.db
# FIRST_ADMIN_EMAIL=you@example.com
# FIRST_ADMIN_NAME=Your Name
# FIRST_ADMIN_PASSWORD=
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Bishnoi One
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]
```

The sign-in settings are only where Platform starts: after that, **Settings →
Security** in the app changes them.

</details>

<details>
<summary><b>Pharmacy</b> (API :8307)</summary>

`bishnoi-pharmacy/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/pharmacy.db
# FIRST_ADMIN_EMAIL=you@example.com
# FIRST_ADMIN_NAME=Your Name
# FIRST_ADMIN_PASSWORD=
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# EXPIRY_WARNING_DAYS=90
# PRESCRIPTION_VALID_DAYS=180
# ORG_NAME=Bishnoi One
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]
# INTEGRATION_KEYS=["crm:<the CRM's PHARMACY_API_KEY>"]
```

</details>

<details>
<summary><b>In-Licensing</b> (API :8306) and <b>Regulatory</b> (API :8308)</summary>

Only the API exists so far. In the one app, `/in-licensing` and `/regulatory` show "Coming soon".

`bishnoi-in-licensing/backend/.env` (for Regulatory, use
`sqlite:///.data/regulatory.db`)

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/licensing.db
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Bishnoi One
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]
```

</details>

### Table prefixes

Every table name starts with its app's prefix, so all the apps can share one
database without clashing:

| App | Prefix | | App | Prefix |
|---|---|---|---|---|
| Admin | `nbad_` | | Inventory | `nbin_` |
| CRM | `nbcm_` | | Platform | `nbpl_` |
| Finance | `nbfi_` | | Pharmacy | `nbph_` |
| In-Licensing | `nbil_` | | Regulatory | `nbrg_` |

---

## 7. Benchmarks: what we build to

Every app is built and reviewed against the [`benchmarks/`](benchmarks/README.md)
folder. It says, feature by feature, **which product does it best**, where
each of our apps stands today, and what we decided to do about it.

### The five benchmarks

Bishnoi One is built for **pharma distribution** first. Each benchmark is the
reference for what it does best:

| Benchmark | The reference for |
|---|---|
| **Salesforce** | Custom fields, layouts, sharing, validation, reporting, the sales pipeline |
| **SAP** | Master data and pricing: one party with roles, condition-based pricing, dated org structures |
| **Odoo** | The closest match to how we're built: one timeline per record, one filter shown as table, board or chart; tax set per country |
| **Marg ERP** | Pharma distribution: keyboard entry, batches and expiry, trade schemes, receivables |
| **Veeva** | Pharma field work: structured doctor visits, call plans, offline, records locked once submitted |

### The files

| File | What it's for |
|---|---|
| [benchmark-matrix.md](benchmarks/benchmark-matrix.md) | **The benchmark.** One row per capability: the reference product, "Ours today" per app, and the decision |
| [patterns-to-adopt.md](benchmarks/patterns-to-adopt.md) | Patterns every app is built to, whichever app it is |
| [decisions.md](benchmarks/decisions.md) | The product decisions the rows depend on |
| [best-of-breed.md](benchmarks/best-of-breed.md) | Notes on what each benchmark does, and why it matters to us |

Each row's decision is **ADOPT** (build it the benchmark's way), **ADAPT**
(our own version; the row says why), **HAVE** (we already do it well
enough), **SKIP** (not for us), or **open** (not decided yet: get the
decision before building it).

### Decided so far (2026-09-25)

| Question | Decided |
|---|---|
| Who we mainly build for | **Pharma distribution** |
| Country and tax | **Several countries**: a tax engine with a pack per country. **The Philippines first** (VAT, BIR invoices). |
| Pricing, quotes and invoices | **Pricing rules + invoices**: ordered, dated price rules an admin sets, with tax last; then invoices, payments and ageing in Finance. **Sales orders live in Bishnoi One Orders**, outside this repo. |
| Leads and the pipeline | **Deals on customers**: a stage, an expected value, a forecast category. No separate lead record. |
| KPIs and targets | **Settings → KPIs**: an administrator defines what each person's month is measured by (13 measures the CRM counts, narrowed by activity kind, visit outcome or product, or entered by hand), who it's for, and from what share of the target it's on target or slightly behind. **KPIs → Targets**: monthly targets per person and per team (a team's own, or its people's added up). **KPIs**: a scorecard, one's own or the team's. Revenue won and the four field goals are built-in KPIs. |
| Visit record | A visit records the **products discussed**, in order, each with its key message and the doctor's reaction, and the **next visit's objective**, shown when the next visit is logged. **Field work** shows a month's products detailed and how doctors took them. |
| Lead source | Customers and deals share one list (Settings → Deal stages); a new deal starts with its customer's. |
| Duplicates | **Customers → Possible duplicates** finds lookalike customers and contacts (same phone however it's written, same email, same or similar name) and merges two into one with all their history. A merged id still leads to the one kept. Merging needs Delete. |
| Email notifications | A quote waiting for approval is emailed to its approvers, and the decision to the rep, through an email delivery service's SMTP. Off until `EMAIL_ENABLED=true`; see `bishnoi-crm/backend/.env.example`. |
| Working without signal | **Offline visits and collections** on the phone, synced when there's signal. |

### Where the build is

| Step | Status |
|---|---|
| 1. Tax engine with the Philippines pack (Finance → **Tax**) | Done |
| 2. Price rules in the CRM (**Settings → Price rules**), tax from Finance | Done |
| 3. Invoices, payments and receivables ageing (Finance) | Done |
| 4. Deals (CRM → **Deals**, **Settings → Deal stages**) and offline visits and collections | Deals done; offline next |

### How to use it

1. **Before you build a feature**, find its row in
   [benchmark-matrix.md](benchmarks/benchmark-matrix.md). If it's `open`,
   get the decision first. If it's ADOPT or ADAPT, build it to the reference
   and to [patterns-to-adopt.md](benchmarks/patterns-to-adopt.md).
2. **When you finish**, update the row's "Ours today" for your app in the
   same pull request.
3. **No row for it?** Add one, with its reference product and "Ours today",
   and leave the decision `open`.

---

## 8. Add a new app

A new app goes in through a **pull request**. You propose it, and GitHub
checks it. The repo owner then reviews and merges it into `main`.

### Step 1: Start a branch

From your clone of the repo ([section 3](#3-clone-download-the-code)):

```
git switch main
git pull
git switch -c add-app/hr
```

Replace `hr` with your app's name.

> Name your branch `add-app/<name>`. **Don't** start it with `bishnoi-`.

### Step 2: Create the app's folder

Name the folder **`bishnoi-<name>`**, using small letters, digits and dashes
only (e.g. `bishnoi-hr`, `bishnoi-field-sales`). Inside it, add:

| What | How |
|---|---|
| `backend/` | the API: start from another app's `backend/` |
| `.gitignore` | copy it from another app |
| `README.md` | copy it from another app, and change the app's name, what it does, its port and how it's deployed |

Don't add a `frontend/`: **Check apps** refuses one in an app folder. The
app's screens go in the one app, `bishnoi-one-app/frontend`, under a path of
their own (see [bishnoi-one-app/README.md](bishnoi-one-app/README.md)).

Pick the next free API port after the last app (currently **8309**).

### Step 3: Commit and push your branch

```
git add .
git commit -m "Add the HR app"
git push -u origin add-app/hr
```

### Step 4: Open a pull request

1. On the repo's GitHub page, click **Compare & pull request** (or go to
   **Pull requests → New pull request**).
2. Set it to merge **`add-app/hr` into `main`**.
3. In the description, say what the app is for and which ports it uses.
4. Click **Create pull request**.

GitHub's **Check apps** check runs by itself. If it shows a red ✗, click
**Details**: it lists what to fix (for example, a missing file or a wrong
folder name). Fix it on your branch, then commit and push again. The check
runs again by itself.

### Step 5: The owner merges it

The repo owner reviews your app and merges it into `main`. From then on,
everyone has it on their next `git pull`.

---

## 9. What happens after you push

**Nothing for you to do.** Your work is on `main`, and your teammates get
it the next time they `git pull`.

Pushing doesn't deploy. Nothing goes online until someone deploys it by hand
([MAINTAINING.md](MAINTAINING.md)).

---

## 10. Rules

1. **Pull before you start, and pull before you push.**
2. **Never force-push** (`git push --force`). It deletes other people's work.
3. **Never commit secrets.** `.env`, `.env.local`, keys and the backend's
   `.data/` folder are already ignored by Git. Don't force them in with
   `git add -f`.
4. **Work on `main`.** If you want a branch for a change, branch from
   `main` and open a pull request back into `main`.
5. **Don't create branches that start with `bishnoi-`.**
6. **Build features to the benchmark.** Every app is measured against
   [`benchmarks/`](benchmarks/README.md) ([section 7](#7-benchmarks-what-we-build-to)): find the feature's row in
   `benchmark-matrix.md` before you build it, follow `patterns-to-adopt.md`,
   and update the row's "Ours today" in the same pull request.

---

## 11. Cheat sheet

| I want to… | Command |
|---|---|
| Clone the repo | `git clone https://github.com/jeydweirdough/nabhi.git bishnoi` |
| Get the latest | `git pull` |
| See what I changed | `git status` / `git diff` |
| Save my changes | `git add .` then `git commit -m "what changed"` |
| Share them | `git pull` then `git push` |
| Push was rejected | `git pull --rebase` then `git push` |
| Undo my edits to one file | `git restore <file>` |
| See history | `git log --oneline` |
| Which branch am I on? | `git branch --show-current` |
| Who am I committing as? | `git config user.name` |
| Run every API and the screens | `npm run one`, then open http://localhost:4301 (from the top of the repo) |
| Run one API | `npm run bishnoi-crm` (from the top of the repo) |
| Start a new app | `git switch -c add-app/<name>`, then [section 8](#8-add-a-new-app) |

---

*Looking after the repo (adding people, reviewing new apps, deploying)? See
[MAINTAINING.md](MAINTAINING.md).*
