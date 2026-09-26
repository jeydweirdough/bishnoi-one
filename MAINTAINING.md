# Looking after the Nabhi repo

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
| **Sync branches** (`sync-branches.yml`) | any push to `main` or a `nabhi-*` branch, every 30 minutes, or by hand | Merges each app branch's new work into `main`, then rebuilds every app branch from `main` and pushes it. It also creates the branch for a new app folder. |
| **Check apps** (`check-apps.yml`) | every pull request into `main` | Checks each `nabhi-*` folder: name, `frontend/`, `backend/`, `.gitignore`, `GIT-GUIDE.md`, the workflow copy, and no secrets. |
| **Deploy** (`deploy.yml`) | only by hand: **Run workflow** | Deploys to Vercel the apps you tick ([below](#deployments-on-vercel-only-when-you-ask)). |

Set these once:

1. **Settings → Actions → General → Workflow permissions: Read and write.**
2. **Add a `SYNC_TOKEN` secret.** GitHub's own token isn't allowed to push
   workflow files, and each app branch carries a copy of the sync workflow.
   With this token, the sync can push those too, including a new app's
   branch.
   1. Create the token: your profile → **Settings → Developer settings →
      Personal access tokens → Fine-grained tokens → Generate new token**.
   2. Repository access: only `jeydweirdough/nabhi`.
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
   `nabhi-<name>` becomes the app's branch, and renaming it later means
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
`nabhi-<name>` branch. Afterwards:

- Add the app to the layout, branch and port tables in `README.md`, and
  update the "next free ports" in README section 8.
- Tell the author its branch name, and delete the `add-app/<name>` branch
  (GitHub offers a button after the merge).

---

## Deployments on Vercel: only when you ask

Nothing deploys by itself. Vercel doesn't build from Git (every app's
`vercel.json`, screens and API: `git.deploymentEnabled: false`), and the
**Deploy** action (`.github/workflows/deploy.yml`) runs only when you press
its button:

1. **Actions → Deploy → Run workflow** (branch `main`).
2. Tick the apps to put online. Each says whether it's on Vercel, e.g. "CRM
   (on Vercel: screens + API)" or "Pharmacy (not on Vercel yet)".
3. Pick **screens and API**, **screens only** or **API only**. Tick **Skip a
   part that hasn't changed** to leave out any that are already up to date.
4. **Run workflow.** The run's summary is a table of every app: whether you
   ticked it, its Vercel projects, and what this run did with it. An app
   that isn't on Vercel is listed as skipped, never an error.

- It deploys `main` as it is, to production. Commits get no Vercel checks,
  and the app branches get no preview builds.
- Each project's last deployed commit is the tag `deployed/<project>` (the
  repo's Tags show what's live).
- Which folder goes to which project: `.github/deploy.json`. When an app gets
  its Vercel projects, add them there, and change its "(not on Vercel yet)"
  in `deploy.yml` to "(on Vercel: screens + API)".

Set up once:

1. Vercel → your avatar → **Account Settings → Tokens → Create**, on the
   account the Nabhi projects are in, with no expiry or a long one.
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
projects on Vercel (Root Directory `nabhi-<app>/frontend` and
`nabhi-<app>/backend`), add them to `deploy.json`, then tick it here.

---

## Linking the CRM to Inventory

The CRM's products come from Inventory, with their SRP, and it shows
Inventory's stock on Products and on new quotes. The two APIs talk through a
shared key. Set up once, on Vercel (each project → **Settings → Environment
Variables**, then redeploy it):

1. Make a key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. **nabhi-inventory-backend:** `INTEGRATION_KEYS` = `["crm:<the key>"]`.
3. **nabhi-crm-backend:**
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
rules. Finance isn't on Vercel yet, so today this link works when both run on
the same computer or network.

1. Make a key, as above. Use a different one from the Inventory link.
2. **Finance API** (`nabhi-finance/backend/.env`): `INTEGRATION_KEYS` =
   `["crm:<the key>"]`.
3. **CRM API** (`nabhi-crm/backend/.env`): `FINANCE_API_URL` = Finance's API
   address (e.g. `http://127.0.0.1:8303`) and `FINANCE_API_KEY` = the key.
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

The same link carries **fund requests** (cash advances):

- **In the CRM:** a salesperson or field agent submits a request, and their
  Team Lead approves or declines it (**Field work → Fund requests**). An
  admin sets the purposes, and whether each is subject to liquidation, under
  **Settings → Fund purposes**.
- **In Finance:** an approved request goes to Finance (**Fund requests**),
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

## Linking the CRM to Nabhi Order

Nabhi Order is its own application. On a quote, **Raise order** sends the quote
to it; the CRM keeps the order number it answers with, so a quote is ordered
once. The button is off until the quote is approved and its guarantee letter is
checked.

On the CRM API (`nabhi-crm/backend`, and Vercel):

| Variable | Value |
|---|---|
| `ORDERS_API_URL` | Nabhi Order's API, e.g. `https://orders-api.example.com` |
| `ORDERS_API_KEY` | The key Nabhi Order gave the CRM |

The CRM calls `POST {ORDERS_API_URL}/orders` with the headers `X-Nabhi-Key`
and `Idempotency-Key` (the quote's id, the same on a retry), and expects
`{"id", "number"}` back, with an optional `"url"` for the "Order SO-..." link.
The payload is described at the top of `nabhi-crm/backend/app/orders.py`; to
see it for a real quote, call `GET /quotes/{id}/order-payload` on the CRM API.

The printed quotation (**Print** on a quote) takes its letterhead from
Settings, Company and quotes: business address, TIN, and phone or email.

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

1. Make two channels, e.g. `#nabhi-announcements` and `#nabhi-logs`. Keep
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
  bash scripts/sync-branches.sh nabhi-crm       # just one app
  ```

---

## Changing the sync workflow

`.github/workflows/sync-branches.yml` has a copy in each app folder
(`nabhi-*/.github/workflows/`). Each app branch needs its copy, because
GitHub only runs the workflows in the branch that was pushed. Keep all the
copies identical: Check apps fails a pull request if they differ.

After editing, copy it to every app, then stage them all:

```
for d in nabhi-*/; do cp .github/workflows/sync-branches.yml "$d.github/workflows/"; done
git add .github "nabhi-*/.github/*"
```

With `SYNC_TOKEN` set, pushing `main` is enough: the sync carries the copies
to the app branches. Without it, also run `bash scripts/sync-branches.sh`
once by hand.
