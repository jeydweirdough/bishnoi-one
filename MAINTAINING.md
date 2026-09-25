# Looking after the Nabhi repo

This page is for the repo owner. Everyone else only needs
[README.md](README.md).

---

## Adding people

Repo → **Settings → Collaborators → Add people**. They get an email
invitation, and can push once they accept it. Point them to the README.

---

## One-time GitHub setup for the actions

The repo has two actions, in `.github/workflows/`:

| Action | Runs when | What it does |
|---|---|---|
| **Sync branches** (`sync-branches.yml`) | any push to `main` or a `nabhi-*` branch, every 30 minutes, or by hand | Merges each app branch's new work into `main`, then rebuilds every app branch from `main` and pushes it. It also creates the branch for a new app folder. |
| **Check apps** (`check-apps.yml`) | every pull request into `main` | Checks each `nabhi-*` folder: name, `frontend/`, `backend/`, `.gitignore`, `GIT-GUIDE.md`, the workflow copy, and no secrets. |

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
into `main` (README section 6). Before merging:

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
  update the "next free ports" in README section 6.
- Tell the author its branch name, and delete the `add-app/<name>` branch
  (GitHub offers a button after the merge).

---

## Deployments on Vercel: only what changed

Vercel doesn't build anything from Git by itself (each `vercel.json`:
`git.deploymentEnabled: false`). The **Deploy** action
(`.github/workflows/deploy.yml`) does, after every push to `main` and every
sync:

- It deploys only the Vercel projects whose folder changed since that
  project's last deploy, to production. A commit to `nabhi-crm/backend`
  deploys the CRM API and nothing else. Commits get no Vercel checks, and the
  app branches get no preview builds.
- Each project's last deployed commit is the tag `deployed/<project>` (the
  repo's Tags show what's live). A deploy that fails (Vercel down, the day's
  limit reached) is tried again by the next run.
- Which folder goes to which project: `.github/deploy.json`. When an app gets
  a Vercel project, add its line there (a folder not listed is never deployed).

Set up once:

1. Vercel → your avatar → **Account Settings → Tokens → Create**: scope it
   to the team (Jade Atyla's projects), no expiry or a long one.
2. GitHub → the repo → **Settings → Secrets and variables → Actions → New
   repository secret**: `VERCEL_TOKEN`, the token.

To deploy one project now, changed or not: **Actions → Deploy → Run
workflow**, and type its project name (e.g. `nabhi-crm-backend`).

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
