# Orbit

Orbit is a set of separate web apps (Admin, Sales, Finance, Inventory, and
more) kept in one GitHub repo. This page explains how to get the code onto your
computer, keep it up to date, and share your changes.

Repo: **https://github.com/jeydweirdough/orbit**

Each app folder also has its own `GIT-GUIDE.md`, a shorter version of this
page for people who work on that app only.

---

## Start here: which setup is yours?

| You work on… | Use | Go to |
|---|---|---|
| **One app only** (e.g. just Sales) | a **single-app clone** | [Clone one app](#option-a-clone-one-app-most-people) |
| **Several apps**, or you look after the repo | a **full clone** | [Clone everything](#option-b-clone-everything) |

Not sure? Pick **one app**. You can always clone everything later.

---

## 1. How the repo is laid out

Each app is a complete web app in its own folder, with two parts:

- **`frontend/`**: the screens (Next.js)
- **`backend/`**: the API (Python, FastAPI)

The apps don't depend on each other. Each has its own API, its own settings
file, its own database and its own sign-in.

```
orbit/
├── orbit-admin/          screens :4300   API :8300
├── orbit-sales/          screens :4302   API :8302
├── orbit-finance/        screens :4303   API :8303
├── orbit-inventory/      screens :4304   API :8304
├── orbit-platform/       screens :4305   API :8305
├── orbit-in-licensing/   screens :4306   API :8306   (screens not built yet)
├── orbit-pharmacy/       screens :4307   API :8307   (screens not built yet)
├── orbit-regulatory/     screens :4308   API :8308   (screens not built yet)
├── scripts/sync-branches.sh
└── .github/workflows/sync-branches.yml
```

Tip: an app's API port is its screens' port + 4000.

### Branches

The repo has one branch with everything, plus one branch per app:

| Branch | What's in it |
|---|---|
| `main` | **Everything**: every app in its own folder |
| `orbit-admin` | Only the Admin app |
| `orbit-sales` | Only the Sales app |
| `orbit-finance` | Only the Finance app |
| `orbit-inventory` | Only the Inventory app |
| `orbit-platform` | Only the Platform app |
| `orbit-in-licensing`, `orbit-pharmacy`, `orbit-regulatory` | Apps whose screens aren't built yet |

An app branch holds the same files as that app's folder on `main`. **GitHub
keeps them matched for you:** push to either one and, about a minute later,
the other has your change too (see [section 5](#5-how-main-and-the-app-branches-stay-in-sync)).

```
main                          app branches
├── orbit-admin/   ◄──sync──►  orbit-admin
├── orbit-sales/   ◄──sync──►  orbit-sales
└── ...
```

---

## 2. First-time setup (once per computer)

### Step 1: Install the tools

| Tool | What it's for | Get it |
|---|---|---|
| Git | cloning, pulling, pushing | https://git-scm.com (on Windows this also installs **Git Bash**) |
| Node.js (LTS) | running the screens | https://nodejs.org |
| uv | running the Python API | https://docs.astral.sh/uv/ |

### Step 2: Tell Git who you are

Every commit carries your name, and GitHub shows it.

```
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

To keep your real email out of the history, use your GitHub "noreply" address
(GitHub → Settings → Emails).

### Step 3: Sign in to GitHub

The first time you push, Git opens a browser window to sign in to GitHub.
Sign in, and Git remembers you from then on.

**On the shared office machine**, these shortcuts switch accounts for the
current repo:

```
git use-jeyd       # commit and push as jeydweirdough
git use-backend    # commit and push as backenddepartment
git who            # show which account is active
```

Run `git who` before you commit, so your work goes under the right name.

---

## 3. Clone (download the code)

Open a terminal (PowerShell, Git Bash or Terminal) in the folder where you
keep your projects, then pick one option.

### Option A: Clone one app (most people)

```
git clone -b orbit-sales --single-branch https://github.com/jeydweirdough/orbit.git orbit-sales
cd orbit-sales
```

Replace **both** `orbit-sales`s with your app (`orbit-admin`,
`orbit-finance`, …). You get only that app, with `frontend/` and `backend/` at
the top.

### Option B: Clone everything

```
git clone https://github.com/jeydweirdough/orbit.git
cd orbit
```

You get `main`: every app, each in its own folder.

### Then: create your settings files

Passwords and other secrets are never stored in Git. Every app includes
example files. Copy them once:

| Part | Copy this… | …to this |
|---|---|---|
| API | `backend/.env.example` | `backend/.env` |
| Screens | `frontend/.env.example` | `frontend/.env.local` |

[Section 7](#7-running-an-app) shows how to install and run the app.

---

## 4. Everyday work

The daily routine is **pull → work → commit → pull → push**.

### Step 1: Pull before you start

```
git pull
```

This downloads what everyone else pushed since last time.

### Step 2: Work

Edit files as usual. To see what you've changed at any point:

```
git status      # which files changed
git diff        # the exact lines that changed
```

### Step 3: Commit (save a checkpoint)

```
git add .
git commit -m "Add expiry column to stock list"
```

Say *what changed* in the message: "Fix total on the invoice page", not
"update" or "fix".

### Step 4: Pull again, then push

```
git pull
git push
```

Where does `git push` send your work?

- **Single-app clone:** to that app's branch (e.g. `orbit-sales`).
- **Full clone:** to `main`.

Both are fine. GitHub copies your change to the other side for you.

### If `git push` is rejected

This means someone pushed before you. Bring in their work first, then push:

```
git pull --rebase
git push
```

### If Git reports a conflict

A conflict means you and someone else changed the same lines. Git lists the
files. Open each one and find the markers:

```
<<<<<<< yours
your version
=======
their version
>>>>>>> theirs
```

Edit it down to the correct final code, delete the three marker lines, then:

```
git add .
git rebase --continue
git push
```

Stuck? `git rebase --abort` puts everything back the way it was before
`git pull --rebase`.

### Bigger changes: use your own branch (optional, full clone)

Put unfinished work on its own branch, so `main` stays working:

```
git switch -c feature/stock-alerts
# ...commit as usual...
git push -u origin feature/stock-alerts
```

On GitHub, open a pull request from `feature/stock-alerts` into **`main`**,
and merge it when it's ready. Feature branches always go into `main`, never
into an app branch.

---

## 5. How `main` and the app branches stay in sync

**You don't need to do anything.** After every push to `main` or to an app
branch, GitHub runs the **Sync branches** action. It goes through **every
app**, whichever branch you pushed, so no branch is left behind. For each
app, it:

1. Copies new work from the app branch into that app's folder on `main`.
2. Copies `main`'s version of the folder back to the app branch.

It also runs every 30 minutes as a safety net. Watch it on the repo's
**Actions** tab.

The next time you `git pull`, you get the changes that were pushed on the
other side.

### If a sync fails (red ✗ on the Actions tab)

This almost always means the same lines were changed on `main` and on the app
branch. The failed run's summary says what to do. In short, on a **full
clone**, in **Git Bash**:

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

### For whoever looks after the repo

- **Run a sync on demand:** Actions → Sync branches → **Run workflow**.
- **Run it by hand:** on a full clone, on `main`, with nothing uncommitted,
  in Git Bash:
  ```
  bash scripts/sync-branches.sh                 # every app
  bash scripts/sync-branches.sh orbit-sales     # just one app
  ```
- **GitHub settings the action needs (once):**
  1. Settings → Actions → General → Workflow permissions: **Read and write**.
  2. Add a **`SYNC_TOKEN`** secret. GitHub's own token isn't allowed to push
     changes to workflow files. With this secret, the action can push them
     too, so every branch gets everything.
     - Create the token: GitHub → your profile → Settings → Developer
       settings → Personal access tokens → **Fine-grained tokens** →
       Generate new token.
     - Repository access: only `jeydweirdough/orbit`.
     - Permissions: **Contents: Read and write** and
       **Workflows: Read and write**.
     - Save it on the repo: Settings → Secrets and variables → Actions →
       New repository secret. Name it `SYNC_TOKEN`.
     - The token expires on the date you choose. When it does, make a new one
       and replace the secret.
  3. If `main` is protected, allow the token's owner (or GitHub Actions) to
     push to it.
- **Without `SYNC_TOKEN`**, the sync still works, except for changes to
  workflow files. Push those yourself: commit and push `main`, then run
  `bash scripts/sync-branches.sh` by hand once.
- **Changing the action file:** it lives at
  `.github/workflows/sync-branches.yml`, with a copy in each app folder
  (`orbit-*/.github/workflows/`). Each app branch needs its copy, because
  GitHub only runs the workflows in the branch that was pushed. Keep all the
  copies the same. To stage them all at once:
  ```
  git add .github "orbit-*/.github/*"
  ```

---

## 6. Rules

1. **Never force-push** (`git push --force`). It deletes other people's work.
2. **Never commit secrets.** `.env`, `.env.local`, keys, and the backend's
   `.data/` folders are already ignored. Don't force them in with
   `git add -f`.
3. **Don't open pull requests from an app branch into `main`.** The sync
   already does that, and the two branches have different folder layouts. If
   GitHub shows a yellow "Compare & pull request" banner after you push to an
   app branch, ignore it.
4. **Pull before you start, and pull before you push.**

---

## 7. Running an app

Every app runs the same way, in **two terminals**. On a full clone, first
`cd orbit-<app>`.

**Terminal 1: the API**

```
cd backend
cp .env.example .env       # first time only
uv sync
uv run main.py
```

**Terminal 2: the screens**

```
cd frontend
cp .env.example .env.local # first time only
npm install
npm run dev
```

Then open the app's screens in your browser:

| App | Screens | API |
|---|---|---|
| Admin | http://localhost:4300 | http://127.0.0.1:8300 |
| Sales | http://localhost:4302 | http://127.0.0.1:8302 |
| Finance | http://localhost:4303 | http://127.0.0.1:8303 |
| Inventory | http://localhost:4304 | http://127.0.0.1:8304 |
| Platform | http://localhost:4305 | http://127.0.0.1:8305 |
| Licensing, Pharmacy, Regulatory | (not built) | 8306, 8307, 8308 |

### Your first account

**Each app has its own sign-in.** An account works in one app only, and
there is no sign-up page. Create the first account from the app's `backend/`
folder:

```
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
```

Use `list`, `password`, `disable` and `enable` to manage accounts afterwards.

### Good to know

- Each API's database is set by `DATABASE_URL` in its `backend/.env`. By
  default it's SQLite, in `backend/.data/`. To try an app against test data,
  point `DATABASE_URL` at a test database.
- Each API has interactive docs at `/docs`, e.g. http://127.0.0.1:8302/docs.
- Run an API's tests with `uv run pytest` in its `backend/` folder.

---

## 8. Adding a new app

1. On `main`, create `orbit-<name>/` with `frontend/` and `backend/`. Copy
   these from another app, then adjust the names and ports:
   - `.gitignore`
   - `GIT-GUIDE.md`
   - `.github/workflows/sync-branches.yml`
   - `backend/`
2. Commit and push `main`.
3. In Git Bash, run `bash scripts/sync-branches.sh orbit-<name>`. This creates
   the app's branch on GitHub.

---

## 9. Cheat sheet

| I want to… | Command |
|---|---|
| Clone one app | `git clone -b <branch> --single-branch https://github.com/jeydweirdough/orbit.git <folder>` |
| Clone everything | `git clone https://github.com/jeydweirdough/orbit.git` |
| Get the latest | `git pull` |
| See what I changed | `git status` / `git diff` |
| Save my work | `git add .` then `git commit -m "message"` |
| Share it | `git pull` then `git push` |
| Push was rejected | `git pull --rebase` then `git push` |
| Undo my edits to one file | `git restore <file>` |
| See history | `git log --oneline` |
| Which branch am I on? | `git branch --show-current` |
| Who am I committing as? | `git config user.name` (or `git who` on the office machine) |
| Sync `main` ⇄ app branches | Automatic after every push. By hand: `bash scripts/sync-branches.sh` |
