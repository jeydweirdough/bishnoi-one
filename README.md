# Nabhi

Nabhi is a set of separate web apps (Admin, CRM, Finance, Inventory, and
more) kept in one GitHub repo. This page shows you how to:

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

Each app is a complete web app in its own folder, with two parts:

- **`frontend/`**: the screens (Next.js)
- **`backend/`**: the API (Python, FastAPI)

The apps don't depend on each other. Each one has its own settings, database
and sign-in.

```
nabhi/
├── nabhi-admin/          screens :4300   API :8300
├── nabhi-crm/            screens :4302   API :8302
├── nabhi-finance/        screens :4303   API :8303
├── nabhi-inventory/      screens :4304   API :8304
├── nabhi-platform/       screens :4305   API :8305
├── nabhi-in-licensing/   screens :4306   API :8306   (screens not built yet)
├── nabhi-pharmacy/       screens :4307   API :8307
└── nabhi-regulatory/     screens :4308   API :8308   (screens not built yet)
```

### Branches

| Branch | What's in it |
|---|---|
| `main` | **Everything**: every app, each in its own folder |
| `nabhi-admin`, `nabhi-crm`, `nabhi-finance`, … | **One app only**, named after it |

An app branch holds the same files as that app's folder on `main`. You can
work on either one; GitHub keeps them matched for you
([section 9](#9-what-happens-after-you-push)).

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
projects, then pick **one** option.

### Option A: One app (most people)

Use this if you work on a single app. Example for CRM:

```
git clone -b nabhi-crm --single-branch https://github.com/jeydweirdough/nabhi.git nabhi-crm
cd nabhi-crm
```

For another app, replace **both** `nabhi-crm`s with its branch name
(`nabhi-admin`, `nabhi-finance`, …). You get only that app, with `frontend/`
and `backend/` right at the top.

### Option B: Everything

Use this if you work across several apps, or to [add a new app](#8-add-a-new-app):

```
git clone https://github.com/jeydweirdough/nabhi.git
cd nabhi
```

You get `main`, with every app in its own folder.

### Then: create your settings files

Passwords and other secrets are never stored in Git. Each app includes
example files instead. On a full clone, `npm run <app>` copies them for you
([section 5](#5-run-an-app)); otherwise copy them once per app:

| Copy this… | …to this |
|---|---|
| `backend/.env.example` | `backend/.env` |
| `frontend/.env.example` | `frontend/.env.local` |

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

That's it. Your work is on GitHub, and the other branch gets it too
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

### The quick way (full clone)

From the top of the repo, one command runs an app's API and screens
together:

```
npm run nabhi-crm
```

The first time, it gets the app ready by itself: it copies the `.env`
example files, makes the API's Python environment (`backend/.venv`, with
`uv sync`) and installs the screens' packages (`npm install`). After that it
only redoes what changed. Each line of output is marked `[api]` or `[web]`,
and **Ctrl+C** stops both.

Every app has one: `npm run nabhi-admin`, `nabhi-crm`, `nabhi-finance`,
`nabhi-inventory`, `nabhi-pharmacy`, `nabhi-platform`, `nabhi-in-licensing`,
`nabhi-regulatory` (the last two run their API only: no screens yet).

| Also | Does |
|---|---|
| `npm run nabhi-crm -- --api` | The API only |
| `npm run nabhi-crm -- --web` | The screens only |
| `npm run nabhi-crm -- --setup` | Gets it ready, starts nothing |
| `npm run setup` | Gets **every** app ready |

It needs only Node.js and uv (step 2): the root `package.json` has no
packages of its own to install.

### As a desktop app

To try an app the way it will be used on a PC, in a window of its own, add
`:app` to its name:

```
npm run nabhi-crm:app
```

It starts the API and the screens as above, then opens them in the app's
own window. The first time, it installs what the window needs (in
`desktop/`). Closing the window stops the app; so does **Ctrl+C**.

Every app with screens has one: `nabhi-admin:app`, `nabhi-crm:app`,
`nabhi-finance:app`, `nabhi-inventory:app`, `nabhi-pharmacy:app` and
`nabhi-platform:app`. To have several open, run each in its own terminal.

| In the window | What happens |
|---|---|
| The app itself | Its own window, taskbar button and sign-in, separate from the other apps |
| A link to another Nabhi app | Opens in that app's window. If that app isn't running, a message says how to start it |
| Sign in with your Nabhi account | Stays in the window, and comes back signed in |
| Any other link (a map, a website) | Opens in your browser |

This is for trying the apps on your own computer. Installers for other PCs
come later.

### The license

A desktop app opens only with the company's license. It is set up once on
each PC, in whichever Nabhi app is opened first, and kept for every Nabhi app
on that PC: an app installed later opens with it straight away, as long as
the license includes that app.

Each company gets three things from us:

| What | Example | Secret? |
|---|---|---|
| Company ID | `NBH-GETMEDS-01` | No |
| Activation key | `7KQ4M-2XD9P-RTH6W-A3CFN-8B5JE` | Yes: give it to their administrator only, apart from the file |
| License file | `NBH-GETMEDS-01.nabhi` | No: it is encrypted, and useless without the key |

The license file says which apps the company has and until when (30 days
by default), and carries each app's database connection. On the PC it is
kept in `%APPDATA%\Nabhi\license.json`, with the activation key locked to
that Windows account (it can't be copied to another PC or account). When it
runs out, the apps warn a week before, keep working three days after, then
stop until a renewed file is chosen (Help > Use a renewed license file).

Issuing and renewing, from `desktop/`:

```
npm run license -- issue           # a new company: Company ID, activation key, file
npm run license -- renew <file>    # a new file with the same IDs: new apps, passwords or expiry
npm run license -- check <file>    # what's inside, passwords hidden
```

Files are written to `desktop/issued/`, which is never committed. To try the
desktop apps on your own PC, add `--local` and type `local` for each app's
database: the apps then keep using their own `backend/.env` databases. Trying
the apps from the repo keeps its license apart from a real one, in
`%APPDATA%\Nabhi development\license.json`.

### By hand (or on a one-app clone)

Every app runs the same way, in **two terminals**. On a full clone, first go
into the app's folder (`cd nabhi-crm`).

**Terminal 1: the API**

```
cd backend
uv sync
uv run main.py
```

**Terminal 2: the screens**

```
cd frontend
npm install
npm run dev
```

Then open the screens in your browser:

| App | Screens | API |
|---|---|---|
| Admin | http://localhost:4300 | http://127.0.0.1:8300 |
| CRM | http://localhost:4302 | http://127.0.0.1:8302 |
| Finance | http://localhost:4303 | http://127.0.0.1:8303 |
| Inventory | http://localhost:4304 | http://127.0.0.1:8304 |
| Platform | http://localhost:4305 | http://127.0.0.1:8305 |
| Pharmacy | http://localhost:4307 | http://127.0.0.1:8307 |
| In-Licensing, Regulatory | (not built) | 8306, 8308 |

### Your first account

Each app has **its own sign-in**, and there's no sign-up page. Create your
account from the app's `backend/` folder:

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
  `listen EACCES: permission denied 0.0.0.0:4302`, Windows has set that port
  aside (Hyper-V, WSL and Docker do this, and it changes from one restart to
  the next). `netsh interface ipv4 show excludedportrange protocol=tcp` shows
  which ports. To keep it away from the Nabhi ports for good, run this once
  in a terminal opened as administrator, then restart the PC:

  ```
  netsh int ipv4 set dynamicport tcp start=49152 num=16384
  netsh int ipv6 set dynamicport tcp start=49152 num=16384
  ```

### Put an app online (Vercel)

Each app is **two Vercel projects** from this repo: its API and its screens.
When you import the repo, set the project's **Root Directory** to the app's
`backend/` or `frontend/` folder.

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

**Every screens project:**

```
API_URL=https://<this app's API address>.vercel.app
NEXT_PUBLIC_NABHI_CRM_URL=https://<the CRM's screens address>.vercel.app
NEXT_PUBLIC_NABHI_INVENTORY_URL=https://<Inventory's screens address>.vercel.app
```

- Add one `NEXT_PUBLIC_NABHI_<APP>_URL` for each other app you've put
  online, so the sidebar's links between apps go to the right place
  ([section 6](#screens-settings-every-app)). These are read when the
  screens are built: redeploy after you set or change one.
- Each app already knows which app it is: `NEXT_PUBLIC_NABHI_APP` isn't
  needed.
- Don't set `SHOW_DEMO_ACCOUNTS` online.

**Linked apps:** the CRM's API also needs `INVENTORY_API_URL`/`KEY` and
`FINANCE_API_URL`/`KEY` for the apps it uses, and each of those APIs needs
the matching `INTEGRATION_KEYS` ([Linking apps](#linking-apps)).

| App | API root directory | Screens root directory |
|---|---|---|
| CRM | `nabhi-crm/backend` | `nabhi-crm/frontend` |
| Inventory | `nabhi-inventory/backend` | `nabhi-inventory/frontend` |
| Pharmacy | `nabhi-pharmacy/backend` | `nabhi-pharmacy/frontend` |
| Platform | `nabhi-platform/backend` | `nabhi-platform/frontend` |

Use the addresses Vercel actually gives your projects (e.g.
`nabhi-inventory-backend.vercel.app`): the API's `ALLOWED_HOSTS` and its
screens' `API_URL` must both name it.

**Pushing doesn't deploy.** To put apps online, the repo owner opens
**Actions → Deploy → Run workflow** on GitHub and ticks the apps; each one
says whether it's on Vercel yet (MAINTAINING.md, "Deployments on Vercel").

If an API can't start, every request to it answers `503` with what's wrong
and which setting to check (`"problem": "database"` → `DATABASE_URL`). The
full error is in the project's logs.

---

## 6. Settings (`.env`) for every app

Each app reads its settings from two files. Git never stores them:

| File | Read by | Starts from |
|---|---|---|
| `backend/.env` | the API | `backend/.env.example` |
| `frontend/.env.local` | the screens | `frontend/.env.example` |

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
| `ORG_NAME` | `Nabhi` | The company name the screens show. |
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
`INTEGRATION_KEYS=["finance:<the key>"]` in the CRM). The app being asked lists a key for each
caller, and the caller sends that key with every request.

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

### Screens settings (every app)

| Setting | Default | What it does |
|---|---|---|
| `API_URL` | this app's API on your computer (`http://127.0.0.1:83xx`) | Where the screens find their own API. Only the screens' server uses it; browsers never see it. |
| `PLATFORM_API_URL` | `http://127.0.0.1:8305` | Nabhi Platform's API, for the announcements above every page. Unreachable: none show. |
| `SHOW_DEMO_ACCOUNTS` | not set | `1` lists the demo accounts beside the sign-in form, for testing. Make them first with `uv run python -m app.tools.users demo` in `backend/`. **Never set it online.** |
| `NEXT_PUBLIC_NABHI_APP` | built in | Which app this is, so the sidebar knows which links go to other apps. Each app already sets its own; only set it to override. |
| `NEXT_PUBLIC_NABHI_<APP>_URL` | the local ports | Where the **other** apps' screens are, for the sidebar's links between apps. Online, set one for each app you deploy (below). |

The `<APP>` names are `EXEC` (Admin), `CRM`, `FINANCE`, `INVENTORY`,
`PLATFORM`, `INLICENSING`, `PHARMACY` and `REGULATORY`, e.g.
`NEXT_PUBLIC_NABHI_FINANCE_URL=https://nabhi-finance.vercel.app`.
`NEXT_PUBLIC_…` settings are built into the screens: **redeploy** after you
change one.

### Complete files, app by app

Ready to copy for your computer. Lines starting with `#` are optional:
remove the `#` to use one.

<details>
<summary><b>Admin</b> (screens :4300, API :8300)</summary>

`nabhi-admin/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/admin.db
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Nabhi
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]
```

`nabhi-admin/frontend/.env.local`

```
API_URL=http://127.0.0.1:8300
SHOW_DEMO_ACCOUNTS=1
# NEXT_PUBLIC_NABHI_APP=exec
```

</details>

<details>
<summary><b>CRM</b> (screens :4302, API :8302)</summary>

`nabhi-crm/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/crm.db
# FIRST_ADMIN_EMAIL=you@example.com
# FIRST_ADMIN_NAME=Your Name
# FIRST_ADMIN_PASSWORD=
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Nabhi
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

`nabhi-crm/frontend/.env.local`

```
API_URL=http://127.0.0.1:8302
SHOW_DEMO_ACCOUNTS=1
# NEXT_PUBLIC_NABHI_APP=crm
```

</details>

<details>
<summary><b>Finance</b> (screens :4303, API :8303)</summary>

`nabhi-finance/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/finance.db
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Nabhi
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]

# Apps allowed to ask Finance for tax
# INTEGRATION_KEYS=["crm:<the CRM's FINANCE_API_KEY>"]
```

`nabhi-finance/frontend/.env.local`

```
API_URL=http://127.0.0.1:8303
SHOW_DEMO_ACCOUNTS=1
# NEXT_PUBLIC_NABHI_APP=finance
```

</details>

<details>
<summary><b>Inventory</b> (screens :4304, API :8304)</summary>

`nabhi-inventory/backend/.env`

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
# ORG_NAME=Nabhi
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]

# Apps allowed to read products and stock
# INTEGRATION_KEYS=["crm:<the CRM's INVENTORY_API_KEY>"]
```

`nabhi-inventory/frontend/.env.local`

```
API_URL=http://127.0.0.1:8304
SHOW_DEMO_ACCOUNTS=1
# NEXT_PUBLIC_NABHI_APP=inventory
```

</details>

<details>
<summary><b>Platform</b> (screens :4305, API :8305)</summary>

`nabhi-platform/backend/.env`

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/platform.db
# FIRST_ADMIN_EMAIL=you@example.com
# FIRST_ADMIN_NAME=Your Name
# FIRST_ADMIN_PASSWORD=
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Nabhi
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]
```

The sign-in settings are only where Platform starts: after that, **Settings →
Security** in the app changes them.

`nabhi-platform/frontend/.env.local`

```
API_URL=http://127.0.0.1:8305
SHOW_DEMO_ACCOUNTS=1
# NEXT_PUBLIC_NABHI_APP=platform
```

</details>

<details>
<summary><b>Pharmacy</b> (screens :4307, API :8307)</summary>

`nabhi-pharmacy/backend/.env`

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
# ORG_NAME=Nabhi
# ORG_CURRENCY=PHP
# ORG_MINOR_UNITS=2
# ORG_LOCALE=en-PH
# ORG_TIMEZONE=Asia/Manila
# ALLOWED_HOSTS=["localhost", "127.0.0.1"]
# CORS_ORIGINS=[]
# INTEGRATION_KEYS=["crm:<the CRM's PHARMACY_API_KEY>"]
```

`nabhi-pharmacy/frontend/.env.local`

```
API_URL=http://127.0.0.1:8307
SHOW_DEMO_ACCOUNTS=1
# NEXT_PUBLIC_NABHI_APP=pharmacy
```

</details>

<details>
<summary><b>In-Licensing</b> (API :8306) and <b>Regulatory</b> (API :8308)</summary>

Only the API exists so far. Their screens have no settings yet.

`nabhi-in-licensing/backend/.env` (for Regulatory, use
`sqlite:///.data/regulatory.db`)

```
ENVIRONMENT=development
# DATABASE_URL=sqlite:///.data/licensing.db
# SESSION_HOURS=10
# LOGIN_ATTEMPTS=5
# LOGIN_LOCKOUT_MINUTES=15
# ORG_NAME=Nabhi
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

Nabhi is built for **pharma distribution** first. Each benchmark is the
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
| Pricing, quotes and invoices | **Pricing rules + invoices**: ordered, dated price rules an admin sets, with tax last; then invoices, payments and ageing in Finance. **Sales orders live in Nabhi Orders**, outside this repo. |
| Leads and the pipeline | **Deals on customers**: a stage, an expected value, a forecast category. No separate lead record. |
| Sales targets | A monthly **revenue target** per seller (Deals → Results → Set targets); a team's is its people's added up. Won deals count against it, on Deals → Results and on the home page. |
| Visit record | A visit records the **products discussed**, in order, each with its key message and the doctor's reaction, and the **next visit's objective**, shown when the next visit is logged. **Field work** shows a month's products detailed and how doctors took them. |
| Lead source | Customers and deals share one list (Settings → Deal stages); a new deal starts with its customer's. |
| Duplicates | **Customers → Possible duplicates** finds lookalike customers and contacts (same phone however it's written, same email, same or similar name) and merges two into one with all their history. A merged id still leads to the one kept. Merging needs Delete. |
| Email notifications | A quote waiting for approval is emailed to its approvers, and the decision to the rep, through an email delivery service's SMTP. Off until `EMAIL_ENABLED=true`; see `nabhi-crm/backend/.env.example`. |
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
checks it. The repo owner then reviews and merges it, and your app gets its
own branch.

### Step 1: Clone everything and start a branch

You need the full repo ([Option B](#option-b-everything)). Then:

```
git switch main
git pull
git switch -c add-app/hr
```

Replace `hr` with your app's name.

> Name your branch `add-app/<name>`. **Don't** start it with `nabhi-`: those
> names are kept for the app branches.

### Step 2: Create the app's folder

Name the folder **`nabhi-<name>`**, using small letters, digits and dashes
only (e.g. `nabhi-hr`, `nabhi-field-sales`). This becomes your app's branch
name. Inside it, add:

| What | How |
|---|---|
| `frontend/` | the screens: start from another app's `frontend/` |
| `backend/` | the API: start from another app's `backend/` |
| `.gitignore` | copy it from another app |
| `GIT-GUIDE.md` | copy it from another app, and change the app name and ports |
| `.github/workflows/sync-branches.yml` | copy `.github/workflows/sync-branches.yml` from the top of the repo, **unchanged** |

Pick the next free ports: the screens get the next number after the last app
(currently **4309**), and the API is that + 4000 (**8309**).

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

The repo owner reviews your app and merges it into `main`. About a minute
later, your app has **its own branch, named after its folder**
(`nabhi-hr`). From then on, anyone can clone just your app:

```
git clone -b nabhi-hr --single-branch https://github.com/jeydweirdough/nabhi.git nabhi-hr
```

---

## 9. What happens after you push

**Nothing for you to do.** About a minute after any push to `main` or to an
app branch, GitHub's **Sync branches** action runs:

- Push to an **app branch** (e.g. `nabhi-crm`): your work is copied into
  that app's folder on `main`.
- Push to **`main`**: each app's folder is copied to its app branch.

Every branch is brought up to date on every run, so none is left behind. Your
teammates get your work the next time they `git pull`.

You can watch it on the repo's **Actions** tab. If a run there shows a red ✗
after your push, tell the repo owner. It usually means the same lines were
changed on `main` and on an app branch, and it needs sorting out by hand.

---

## 10. Rules

1. **Pull before you start, and pull before you push.**
2. **Never force-push** (`git push --force`). It deletes other people's work.
3. **Never commit secrets.** `.env`, `.env.local`, keys and the backend's
   `.data/` folder are already ignored by Git. Don't force them in with
   `git add -f`.
4. **Don't open pull requests from an app branch into `main`.** The sync
   already does that. If GitHub shows a yellow "Compare & pull request"
   banner after you push to an app branch, ignore it. (Pull requests from an
   `add-app/…` or `feature/…` branch are fine.)
5. **Don't create branches that start with `nabhi-`.** Those are the app
   branches, and the sync manages them.
6. **Build features to the benchmark.** Every app is measured against
   [`benchmarks/`](benchmarks/README.md) ([section 7](#7-benchmarks-what-we-build-to)): find the feature's row in
   `benchmark-matrix.md` before you build it, follow `patterns-to-adopt.md`,
   and update the row's "Ours today" in the same pull request.

---

## 11. Cheat sheet

| I want to… | Command |
|---|---|
| Clone one app | `git clone -b <app> --single-branch https://github.com/jeydweirdough/nabhi.git <app>` |
| Clone everything | `git clone https://github.com/jeydweirdough/nabhi.git` |
| Get the latest | `git pull` |
| See what I changed | `git status` / `git diff` |
| Save my changes | `git add .` then `git commit -m "what changed"` |
| Share them | `git pull` then `git push` |
| Push was rejected | `git pull --rebase` then `git push` |
| Undo my edits to one file | `git restore <file>` |
| See history | `git log --oneline` |
| Which branch am I on? | `git branch --show-current` |
| Who am I committing as? | `git config user.name` |
| Run an app (API + screens) | `npm run nabhi-crm` (from the top of a full clone) |
| Start a new app | `git switch -c add-app/<name>`, then [section 8](#8-add-a-new-app) |

---

*Looking after the repo (sync settings, tokens, reviewing new apps)? See
[MAINTAINING.md](MAINTAINING.md).*
