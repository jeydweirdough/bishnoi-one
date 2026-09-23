# Git guide — Orbit

How to clone, pull and push the Orbit repo, and how the per-app branches work.
Each app folder also has its own `GIT-GUIDE.md` for people working on just that
app.

Repo: **https://github.com/jeydweirdough/orbit**

---

## 1. How the repo is laid out

Every app is its own webapp, in its own folder, with two parts:
**`frontend/`** (its screens, Next.js) and **`backend/`** (its API, Python /
FastAPI). The apps don't depend on each other. Each has its own API, its own
`.env` and its own database.

```
orbit/
├── orbit-admin/          frontend/ :4300   backend/ :8300
├── orbit-sales/          frontend/ :4302   backend/ :8302
├── orbit-finance/        frontend/ :4303   backend/ :8303
├── orbit-inventory/      frontend/ :4304   backend/ :8304
├── orbit-platform/       frontend/ :4305   backend/ :8305
├── orbit-in-licensing/   frontend/ :4306   backend/ :8306   (screens not built yet)
├── orbit-pharmacy/       frontend/ :4307   backend/ :8307   (screens not built yet)
├── orbit-regulatory/     frontend/ :4308   backend/ :8308   (screens not built yet)
└── scripts/sync-branches.sh
```

An app's API port is its screens' port + 4000, so each pair is easy to spot.
The screens reach their own API through `API_URL` in `frontend/.env.local`.

One repo, two kinds of branch:

| Branch | What's in it | Who uses it |
|---|---|---|
| `main` | **Everything**: every app in its own folder, plus `scripts/` | Anyone working across apps, and whoever keeps the branches in sync |
| `orbit-admin` | Only the Admin app (`frontend/`, `backend/`) | Admin developers |
| `orbit-sales` | Only the Sales app | Sales developers |
| `orbit-finance` | Only the Finance app | Finance developers |
| `orbit-inventory` | Only the Inventory app | Inventory developers |
| `orbit-platform` | Only the Platform app | Platform developers |
| `orbit-in-licensing`, `orbit-pharmacy`, `orbit-regulatory` | Apps whose screens aren't built yet | — |

`main` is the source of truth. An app branch holds the same files as that
app's folder on `main`, and the two are kept in step by
`scripts/sync-branches.sh` (section 5).

```
main                          app branches
├── orbit-admin/   ◄──sync──►  orbit-admin    (frontend/, backend/)
├── orbit-sales/   ◄──sync──►  orbit-sales    (frontend/, backend/)
└── ...
```

---

## 2. First-time setup (once per computer)

Install Git from https://git-scm.com, then tell Git who you are. Every commit
carries this name, and it's what GitHub shows.

```
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

Tip: use your GitHub "noreply" email (GitHub → Settings → Emails) if you don't
want your real address to appear in the history.

On the shared office machine, two shortcuts switch between accounts for the
current repo:

```
git use-jeyd       # commit and push as jeydweirdough
git use-backend    # commit and push as backenddepartment
git who            # show which account is active
```

Run `git who` before you commit, so your work shows up under the right name.

---

## 3. Cloning

### Just one app (most people)

```
git clone -b orbit-sales --single-branch https://github.com/jeydweirdough/orbit.git orbit-sales
cd orbit-sales
```

Replace `orbit-sales` with the app you need (both places). `--single-branch`
downloads only that app, not the others. The folder you get has the app's
files at the top, ready to install and run.

### The whole repo

```
git clone https://github.com/jeydweirdough/orbit.git
cd orbit
```

You land on `main` with every app in its own folder. To use the sync script
(section 5) you need this full clone.

### After cloning: files that are not in Git

Secrets and local data are never committed. Each part has an example to copy:

| Part | Create | From |
|---|---|---|
| Screens | `orbit-<app>/frontend/.env.local` | `frontend/.env.example` |
| API | `orbit-<app>/backend/.env` | `backend/.env.example` |

Then install: `npm install` in `frontend/`, and `uv sync` in `backend/`.
Each app's `GIT-GUIDE.md` has the exact steps to run it.

---

## 4. Everyday work

### Get the latest changes

```
git pull
```

Do this before you start working, and again before you push.

### Save and share your work

```
git status                      # see what changed
git add .                       # stage everything that changed
git commit -m "Fix total on the invoice page"
git push
```

- On a single-app clone, `git push` sends to that app's branch
  (e.g. `orbit-sales`).
- On a full clone, `git push` sends to `main`.

Write commit messages that say *what changed*, e.g. "Add expiry column to stock
list", not "update" or "fix".

### If `git push` is rejected

Someone pushed before you. Pull their work first, then push again:

```
git pull --rebase
git push
```

If Git reports a **conflict**, open the files it lists and look for the
markers:

```
<<<<<<< yours
your version
=======
their version
>>>>>>> theirs
```

Edit each one down to the correct final code and delete the marker lines.
Then:

```
git add .
git rebase --continue
git push
```

Stuck? `git rebase --abort` puts everything back to how it was before
`git pull --rebase`.

### Working on something bigger (optional)

On a full clone, you can keep unfinished work on its own branch:

```
git switch -c feature/stock-alerts      # create and move to a new branch
# ...commit as usual...
git push -u origin feature/stock-alerts
```

Open a pull request on GitHub from `feature/stock-alerts` into `main`, and
merge it when it's ready. Feature branches go into **`main`**, never into an
app branch.

---

## 5. Keeping `main` and the app branches in sync

Pushes land in two places: some people push to `main`, others push to an app
branch. **This happens by itself:** after every push to `main` or to an
`orbit-*` branch, GitHub runs the **Sync branches** action
(`.github/workflows/sync-branches.yml`). For each app, it:

1. Merges anything new pushed to the app branch into that app's folder on `main`.
2. Pushes `main`.
3. Rebuilds the app branch from `main` and pushes it, so app-branch
   developers get `main`'s changes the next time they `git pull`.

Watch it on the repo's **Actions** tab. To run it without pushing anything,
open **Actions → Sync branches → Run workflow**.

The action file is at `.github/workflows/sync-branches.yml` and, as a copy, in
each app folder (`orbit-*/.github/workflows/`). Each app branch needs the copy
because GitHub only runs workflows that are in the branch being pushed. GitHub
won't let the action push changes to workflow files. So when you change these
files, push them yourself: commit on `main`, then run
`bash scripts/sync-branches.sh` by hand once. That run carries the new copies
to the app branches.

The action runs `scripts/sync-branches.sh`, which still works by hand, from a
**full clone**, on `main`, with nothing uncommitted (Git Bash on Windows runs
it as-is):

```
git switch main
bash scripts/sync-branches.sh                 # every app
bash scripts/sync-branches.sh orbit-sales     # just one app
```

### If the sync stops with a conflict

This happens when the same lines were changed on `main` and on the app branch.
The action's run turns red, and its summary says what to do. On your computer,
run the script by hand; it stops partway through the merge:

```
git status                 # lists the files in conflict
# fix the <<<<<<< ======= >>>>>>> markers in each file
git add .
git commit                 # finishes the merge
bash scripts/sync-branches.sh   # run it again to finish (it pushes too)
```

---

## 6. Rules

1. **Never force-push** (`git push --force`) to `main` or any app branch.
   It deletes other people's work.
2. **Never commit secrets.** `.env`, `.env.local`, keys, and the backend's
   `.data/` folders are already ignored. Don't force them in with
   `git add -f`.
3. **Don't open pull requests from an app branch into `main`.** The sync
   script already handles that, and the branches have different folder layouts.
   If GitHub shows a yellow "Compare & pull request" banner after a push,
   ignore it.
4. **Pull before you start, and pull before you push.**

---

## 7. Adding a new app

1. On `main`, create `orbit-<name>/` with `frontend/` and `backend/`. Copy
   the `.gitignore` and `GIT-GUIDE.md` from another app and adjust them, and
   start `backend/` from another app's (change the names and the port).
2. Commit and push `main`.
3. Run `bash scripts/sync-branches.sh orbit-<name>` to create its branch on
   GitHub.

---

## 8. Running an app

Every app runs the same way, in two terminals:

```
cd orbit-<app>/backend              cd orbit-<app>/frontend
cp .env.example .env                cp .env.example .env.local
uv sync                             npm install
uv run main.py                      npm run dev
```

| App | Screens | API |
|---|---|---|
| Admin | http://localhost:4300 | http://127.0.0.1:8300 |
| Sales | http://localhost:4302 | http://127.0.0.1:8302 |
| Finance | http://localhost:4303 | http://127.0.0.1:8303 |
| Inventory | http://localhost:4304 | http://127.0.0.1:8304 |
| Platform | http://localhost:4305 | http://127.0.0.1:8305 |
| Licensing, Pharmacy, Regulatory | (not built) | 8306, 8307, 8308 |

**Each app has its own sign-in.** Its accounts live in its own database and
sign in to that app only, and each app's screens keep their own cookie, so
being signed in to one app doesn't sign you in (or out) of another. There is
no sign-up page. Make the first account in each app's `backend/`:

```
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
```

`list`, `password`, `disable` and `enable` manage them afterwards.

Each API's database comes from `DATABASE_URL` in its own `backend/.env`
(SQLite in `backend/.data/` by default). To try an app against test data,
point that at a test database; nothing else changes. Each API has its
interactive docs at `/docs` and its tests under `uv run pytest`.

---

## 9. Cheat sheet

| I want to… | Command |
|---|---|
| Clone one app | `git clone -b <branch> --single-branch https://github.com/jeydweirdough/orbit.git <folder>` |
| Clone everything | `git clone https://github.com/jeydweirdough/orbit.git` |
| Get the latest | `git pull` |
| See what I changed | `git status` / `git diff` |
| Save my work | `git add .` then `git commit -m "message"` |
| Share it | `git push` |
| Push was rejected | `git pull --rebase` then `git push` |
| Throw away my edits to one file | `git restore <file>` |
| See history | `git log --oneline` |
| Which branch am I on? | `git branch --show-current` |
| Who am I committing as? | `git config user.name` (or `git who` on the office machine) |
| Sync main ⇄ app branches | Automatic after every push (Actions tab). By hand: `bash scripts/sync-branches.sh` |
