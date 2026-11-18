# Bishnoi One

Bishnoi One is a set of business modules (CRM, Inventory, Finance, Pharmacy
and more; office administration is another app, apart from this repo since 2026-11-19) kept in one GitHub repo: **one backend** with every
module's API, and **one web app** with every module's screens and one sign-in.
This page shows you how to:

- get the code onto your computer
- keep it up to date
- share your changes
- run it
- add a new module

Repo: **https://github.com/jeydweirdough/nabhi**

Everyday Git is three commands: **clone** once, then **pull** and **push**.
The rest of this page walks through them.

---

## Contents

1. [How the repo is laid out](#1-how-the-repo-is-laid-out)
2. [Before you start (once per computer)](#2-before-you-start-once-per-computer)
3. [Clone: download the code](#3-clone-download-the-code)
4. [Pull and push: everyday work](#4-pull-and-push-everyday-work)
5. [Run it](#5-run-it)
6. [Settings (`backend/.env`)](#6-settings-backendenv)
7. [Benchmarks: what we build to](#7-benchmarks-what-we-build-to)
8. [Add a new module](#8-add-a-new-module)
9. [What happens after you push](#9-what-happens-after-you-push)
10. [Rules](#10-rules)
11. [Cheat sheet](#11-cheat-sheet)

---

## 1. How the repo is laid out

Bishnoi One is **one backend** and **one app**:

- **`backend/`**: one Python (FastAPI) server, on port **8300**, with every
  module's API in it. Each module is a folder in `backend/modules/` with its own
  routes, permissions, tables (each module's names start with its own prefix)
  and migrations, and answers under its own path: `/platform`, `/crm`,
  `/inventory`, `/finance`, `/admin`, `/pharmacy`, `/in-licensing`,
  `/regulatory`. So `/crm/customers` is the CRM's customers. `GET /health`
  says which modules started. One settings file, `backend/.env`.
- **`bishnoi-one-app/frontend`**: one Next.js app with every module's screens,
  each under its path, on port **4301**. One Bishnoi One sign-in (a Platform
  account) opens every module. See
  [bishnoi-one-app/README.md](bishnoi-one-app/README.md).

```
bishnoi/
├── backend/                the one backend :8300 (uv run main.py)
│   ├── main.py             starts every module, each under its path
│   ├── pyproject.toml      one set of Python packages (uv.lock)
│   └── modules/
│       ├── platform/       /platform      accounts, companies, roles, the Admin Console
│       ├── crm/            /crm
│       ├── inventory/      /inventory
│       ├── finance/        /finance
│       ├── pharmacy/       /pharmacy
│       ├── in_licensing/   /in-licensing
│       └── regulatory/     /regulatory
├── bishnoi-one-app/        the one app :4301 (every module's screens)
├── desktop/                the one app in a window of its own
└── scripts/                run, set up, back up
```

| Module | Screens in the one app | API in the backend |
|---|---|---|
| CRM | `/crm` | `/crm` |
| Inventory | `/inventory` | `/inventory` |
| Finance | `/finance` | `/finance` |
| Pharmacy | `/pharmacy` | `/pharmacy` |
| Admin Console (company administrators) | `/platform` | `/platform` |
| Operations (Bishnoi One's operators) | `/operations` | `/platform` |
| In-Licensing, Regulatory | `/in-licensing`, `/regulatory` ("Coming soon") | `/in-licensing`, `/regulatory` |

The modules still talk to each other the way they did when each was its own
server (over HTTP, with keys the Platform hands out), now at the backend's own
address: `BACKEND_URL` + the module's path ([section 6](#6-settings-backendenv)).

### Work on `main`

Everything is in one repo. Everyone works on `main`: clone the whole repo,
pull, and push. Want a branch for a change? Branch from `main`, but never name
it `bishnoi-…`.

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

You get `main`, with the backend and the one app.

### Then: create your settings files

Passwords and other secrets are never stored in Git. Example files stand in
for them. `npm run one` copies them for you ([section 5](#5-run-it)); to do it
by hand, copy them once:

| Copy this… | …to this |
|---|---|
| `backend/.env.example` | `backend/.env` (the one backend, every module) |
| `bishnoi-one-app/frontend/.env.example` | `bishnoi-one-app/frontend/.env.local` (the screens) |

What each setting means is in [section 6](#6-settings-backendenv). You're
ready. See [Run it](#5-run-it).

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

## 5. Run it

### The quick way

From the top of the repo, one command runs the backend (every module's API)
and the one app's screens:

```
npm run one
```

Then open **http://localhost:4301** and sign in with your Bishnoi One
account. **Ctrl+C** stops everything. The backend starts first; the screens
start once it answers.

The first time, it gets each part ready by itself: it copies the `.env`
example files, makes the backend's Python environment (`backend/.venv`, with
`uv sync`) and installs the screens' packages (`npm install`). After that it
only redoes what changed.

| Also | Does |
|---|---|
| `npm run backend` | The backend only (every module's API, port 8300) |
| `npm run bishnoi-one-app` | The screens only (the backend must be running) |
| `npm run one -- --setup` / `npm run setup` | Gets everything ready, starts nothing |

It needs only Node.js and uv (step 2): the root `package.json` has no
packages of its own to install.

### As a desktop app

To try the one app the way it will be used on a PC, in a window of its own:

```
npm run bishnoi-one-app:app
```

It starts the backend and the screens, then opens them in a window (the first
time, it installs what the window needs, in `desktop/`). Closing the window
stops everything. This is for trying the app on your own computer; installers
for other PCs come later.

### By hand

```
cd backend
uv sync
uv run main.py          # every module's API on http://127.0.0.1:8300, reloading on code changes
```

`GET http://127.0.0.1:8300/health` lists the modules and whether each started.
Each module answers under its path: the CRM's API at
`http://127.0.0.1:8300/crm`, its interactive docs at
`http://127.0.0.1:8300/crm/docs`, and so on for `/platform`, `/inventory`,
`/finance`, `/admin`, `/pharmacy`, `/in-licensing` and `/regulatory`.

The screens are the one app, in `bishnoi-one-app/frontend`; how to run it by
hand is in [bishnoi-one-app/README.md](bishnoi-one-app/README.md).

### Your first account

One Bishnoi One sign-in (a Platform account) opens every module in the one
app. On a new database, the one app's `/setup` page makes the company and its
first administrator (the setup code is in the backend's log). Or use the users
tool, from `backend/`:

```
uv run python -m modules.platform.tools.users add --email you@example.com --name "Your Name" --admin
```

Later, `list`, `password`, `disable` and `enable` manage accounts. Every
module's tools run the same way, from `backend/`:
`uv run python -m modules.<module>.tools.<tool> …`.

### Good to know

- The database is set by `DATABASE_URL` in `backend/.env`. By default each
  module keeps a local SQLite file in `backend/.data/`. Every setting is in
  [section 6](#6-settings-backendenv).
- Each module runs its own migrations when the backend starts. To make a new
  one: `uv run alembic -c modules/<module>/alembic.ini revision -m "what changed"`
  in `backend/`.
- Run one module's tests at a time, in `backend/`:
  `uv run pytest modules/crm/tests` (or one test:
  `uv run pytest modules/crm/tests/test_deals.py::test_name -q`). If
  `uv run pytest` complains about a trampoline, use
  `uv run python -m pytest …`.
- If a module can't start (a setting, its database), only that module answers
  `503` naming the setting to check; the others run. The full error is in the
  backend's log.
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

### Put it online (Coolify)

Bishnoi One runs on the office server, in Coolify, as **two applications**
built from this repo: the backend and the one app. **Pushing doesn't deploy**:
press **Redeploy** in Coolify when you're ready, the backend first. The full
steps, with every setting, are in [MAINTAINING.md](MAINTAINING.md), "Putting
it online".

| Coolify application | Base directory | Start | Port | Settings |
|---|---|---|---|---|
| Backend | `backend` | `uv run uvicorn main:app --host 0.0.0.0 --port 8300` | 8300 | `DATABASE_URL`, `BACKEND_URL` |
| The one app | `bishnoi-one-app/frontend` | `npm run start` | 4301 | `BACKEND_URL`, `ONE_APP_URL` |

- The backend's `BACKEND_URL` and the one app's `BACKEND_URL` are the
  backend's **internal** address (e.g. `http://10.0.1.1:8300`); only the one
  app is public (`ONE_APP_URL=https://one.bishnoi.ai`).
- One `DATABASE_URL` serves every module: each module's tables start with its
  own prefix ([below](#table-prefixes)) and each keeps its own migration
  history. CRM and Inventory make a database per company beside it
  (`bishnoione` → `bishnoione_getmeds`).

**Several companies, one CRM (and one Inventory)** (since 2026-10-05). Each
company has a database of its own, beside `DATABASE_URL` with the company's
short name added: `bishnoione` → `bishnoione_getmeds`; on this computer
`crm.db` → `crm-getmeds.db`. The module makes each company's database the
first time that company signs in, once the company is registered on Bishnoi
One Platform and given the module. Which company a request is for comes from
the sign-in (the session's token starts with it). The tools take
`--company getmeds` (default on this computer: `DEFAULT_COMPANY`).

**Backups of an online database:** put its address in `backend/.env` as
`<MODULE>_BACKUP_FROM` (`CRM_BACKUP_FROM`, `INVENTORY_BACKUP_FROM`,
`ADMIN_BACKUP_FROM`, `PLATFORM_BACKUP_FROM`) and run
`scripts/backup-online-databases.cmd` by hand or nightly with Task Scheduler
(the command is in the file). The last 30 days stay in
`backend/.data/backups/`. To copy this computer's data into an online
database once: `uv run python -m modules.<module>.tools.copy_database --to "<address>"`
in `backend/` (`--setup` copies only the setup, not the day-to-day records).

---

## 6. Settings (`backend/.env`)

The backend reads its settings from one file, and the one app's screens from
another. Git never stores them:

| File | Read by | Starts from |
|---|---|---|
| `backend/.env` | the backend (every module) | `backend/.env.example` |
| `bishnoi-one-app/frontend/.env.local` | the screens (every module) | `bishnoi-one-app/frontend/.env.example` |

On your computer, **every setting has a default that works**, so the copied
example files are enough. Change a setting only when you need what it does.
Online (Coolify), set the same names under the application's **Environment
Variables**. Lists are written as JSON: `["a", "b"]`. Restart the backend (or
`npm run dev`) after you change a file.

**A setting is for every module, or for one.** `DATABASE_URL` in
`backend/.env` (or the environment) applies to every module that has it.
`<MODULE>_<SETTING>` applies to one module and wins over it: `CRM_DATABASE_URL`,
`FINANCE_INTEGRATION_KEYS`… The prefixes are `PLATFORM_`, `CRM_`,
`INVENTORY_`, `FINANCE_`, `ADMIN_`, `PHARMACY_`, `IN_LICENSING_` and
`REGULATORY_` (`backend/modules/module_settings.py`). Every module's settings
are described in its own `backend/modules/<module>/.env.example`.

### The backend's main settings

| Setting | Default | What it does |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` on a server (worked out by itself on Coolify). Production hides the API docs and turns off demo accounts. |
| `DATABASE_URL` | each module's SQLite file in `backend/.data/` | The database. One `postgresql://…` address on the server serves every module ([table prefixes](#table-prefixes)). |
| `BACKEND_URL` | `http://127.0.0.1:8300` | The backend's own address, as the modules reach each other: every module is at `BACKEND_URL` + its path. `PLATFORM_API_URL`, `CRM_API_URL`, `INVENTORY_API_URL`, `FINANCE_API_URL` and `PHARMACY_API_URL` follow it unless set, and the Platform reports these addresses to the modules and the one app (Applications). On the server: its internal address, e.g. `http://10.0.1.1:8300`. |
| `ONE_APP_URL` | `http://localhost:4301` | The one app's address (sign-in redirects, links in emails). Online, `https://one.bishnoi.ai`. |
| `PASS_SIGNING_KEY` | kept in the database | The key the Platform signs passes with. Unset: made on the first start and kept in the database. |
| `SESSION_HOURS` | `10` | How long a sign-in lasts. |
| `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES` | `5`, `15` | Wrong passwords in a row before an account waits, and for how long. |
| `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE` | `Bishnoi One`, `PHP`, `2`, `en-PH`, `Asia/Manila` | The company as the screens show it, until the Platform's Company profile says. |
| `ALLOWED_HOSTS` | this computer's names; any name in production | Host names the backend answers to. |
| `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL` | off, `mock` | Each module's log to Discord. See MAINTAINING.md, "Connecting Discord". |

### Settings only some modules have

| Module | Setting | Default | What it does |
|---|---|---|---|
| CRM, Inventory, Pharmacy, Platform | `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD` | not set | Makes the first administrator on start, **only** while the module has no accounts. Remove the password after you've signed in. |
| CRM, Inventory | `FIRST_ADMIN_COMPANY` | not set | The company whose database gets the `FIRST_ADMIN_*` account. |
| CRM, Inventory | `DEFAULT_COMPANY`, `DEV_COMPANIES` | `getmeds`, `["getmeds","northwind"]` | This computer only: the company a request is for when it doesn't say, and the companies allowed without the Platform. |
| Inventory, Pharmacy | `EXPIRY_WARNING_DAYS` | `90` | A batch expiring within this many days is flagged "expiring soon". |
| Inventory | `DEAD_STOCK_DAYS` | `180` | Stock with nothing moved out for this long counts as dead stock. |
| Pharmacy | `PRESCRIPTION_VALID_DAYS` | `180` | A prescription older than this can't be verified. |
| Platform | `CRON_SECRET` | not set | The nightly events check (`GET /platform/cron/events-check`). |
| Platform | `DISCORD_ANNOUNCEMENTS_WEBHOOK_URL` | not set | Where announcements are kept. |
| CRM, Inventory, Admin, Platform | `BACKUP_FROM` (`CRM_BACKUP_FROM`…) | not set | The online database `scripts/backup-online-databases.cmd` copies. |

### Linking modules

The modules still call each other over HTTP, with a key for each link: the
CRM asks **Inventory** for products and stock, **Finance** for tax and
**Pharmacy** to check quotes marked Rx; **Finance** asks the **CRM** for
customers and **Inventory** for costs. The **addresses** need nothing: each is
`BACKEND_URL` + the module's path. The **keys** come from the Platform: each
module is connected there (Operations > Services and connections), and the
links between them are switched on there; nothing to copy. Without the
Platform, `INTEGRATION_KEYS` (in the module being asked, as `["crm:<key>"]`)
and `<MODULE>_API_KEY` (in the caller) still work, set with the module's
prefix where two modules differ (e.g. `CRM_INTEGRATION_KEYS`). A missing link
turns the feature off; nothing breaks.

### Screens settings (the one app)

`bishnoi-one-app/frontend/.env.local`. Only the one app's server talks to the
backend; browsers never do.

| Setting | Default | What it does |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8300` | The one backend: each module's API is `BACKEND_URL` + its path. Online, the backend's internal address. |
| `ONE_APP_URL` | `http://localhost:4301` | The one app's own address, as the Platform knows it (online, `https://one.bishnoi.ai`; the backend's `ONE_APP_URL` must be the same). |

The full list is in `bishnoi-one-app/frontend/.env.example`, and
[bishnoi-one-app/README.md](bishnoi-one-app/README.md) explains it.
### Table prefixes

Every table name starts with its module's prefix, so all the modules share one
database without clashing (**Check apps** checks it):

| Module | Prefix | | Module | Prefix |
|---|---|---|---|---|
| CRM | `nbcm_` | | Inventory | `nbin_` |
| Finance | `nbfi_` | | Platform | `nbpl_` |
| Pharmacy | `nbph_` | | | |
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
| Email notifications | A quote waiting for approval is emailed to its approvers, and the decision to the rep, through an email delivery service's SMTP. Off until `EMAIL_ENABLED=true`; see `backend/modules/crm/.env.example`. |
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

## 8. Add a new module

A new module is a new folder in `backend/modules/`, and its screens are a new
module in the one app. It goes in through a **pull request**: GitHub checks
it, and the repo owner reviews and merges it into `main`.

### Step 1: Start a branch

From your clone of the repo ([section 3](#3-clone-download-the-code)):

```
git switch main
git pull
git switch -c add-module/hr
```

Replace `hr` with your module's name. **Don't** start a branch with `bishnoi-`.

### Step 2: Create the module

In `backend/modules/<name>/` (a Python package: small letters, digits and
`_`), start from a small module (`in_licensing` or `regulatory`) and keep:

| What | Why |
|---|---|
| `__init__.py`, `main.py` (`create_app()`), `config.py` | the module's API and its settings (its own `<NAME>_` prefix in `module_sources`) |
| `alembic.ini`, `migrations/versions/` | its own migration history, with its own version table |
| `tests/` | its tests, run with `uv run pytest modules/<name>/tests` |
| `README.md` | what it does |

Then:

1. Pick a table prefix (`nb` + two letters + `_`) that no module has, and
   start every table name with it. Add it to `PREFIXES` in
   `.github/workflows/check-apps.yml`.
2. Add the module to `MODULES` in `backend/main.py`, with its path.
3. Its screens go in the one app, under a path of their own (see
   [bishnoi-one-app/README.md](bishnoi-one-app/README.md)).

### Step 3: Commit and push your branch

```
git add .
git commit -m "Add the HR module"
git push -u origin add-module/hr
```

### Step 4: Open a pull request

1. On the repo's GitHub page, click **Compare & pull request** (or go to
   **Pull requests → New pull request**).
2. Set it to merge **`add-module/hr` into `main`**.
3. In the description, say what the module is for and its table prefix.
4. Click **Create pull request**.

GitHub's **Check apps** check runs by itself. If it shows a red ✗, click
**Details**: it lists what to fix (a missing folder, a table without the
prefix, a module `backend/main.py` doesn't start). Fix it on your branch, then
commit and push again. The check runs again by itself.

### Step 5: The owner merges it

The repo owner reviews the module and merges it into `main`. From then on,
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
| Run the backend and the screens | `npm run one`, then open http://localhost:4301 (from the top of the repo) |
| Run the backend only | `npm run backend` (or `uv run main.py` in `backend/`) |
| Run one module's tests | `uv run pytest modules/crm/tests` (in `backend/`) |
| Start a new module | `git switch -c add-module/<name>`, then [section 8](#8-add-a-new-module) |

---

*Looking after the repo (adding people, reviewing new modules, deploying)? See
[MAINTAINING.md](MAINTAINING.md).*
