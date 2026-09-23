# Git guide — Orbit

How to clone, pull and push the Orbit repo, and how the per-app branches work.
Each app folder also has its own `GIT-GUIDE.md` for people working on just that
app.

Repo: **https://github.com/jeydweirdough/orbit**

---

## 1. How the repo is laid out

One repo, two kinds of branch:

| Branch | What's in it | Who uses it |
|---|---|---|
| `main` | **Everything**: every app in its own folder, plus `scripts/` | Anyone working across apps, and whoever keeps the branches in sync |
| `orbit-admin` | Only the Admin app, at the top level | Admin developers |
| `orbit-backend` | Only the API | Backend developers |
| `orbit-finance` | Only the Finance app | Finance developers |
| `orbit-inventory` | Only the Inventory app | Inventory developers |
| `orbit-platform` | Only the Platform app | Platform developers |
| `orbit-sales` | Only the Sales app | Sales developers |
| `orbit-in-licensing`, `orbit-pharmacy`, `orbit-regulatory` | Placeholder apps, not built yet | — |

`main` is the source of truth. An app branch holds the same files as that
app's folder on `main`, and the two are kept in step by
`scripts/sync-branches.sh` (section 5).

```
main                         orbit-admin branch
├── orbit-admin/   ◄──sync──►  (the contents of orbit-admin/)
├── orbit-backend/ ◄──sync──►  orbit-backend branch
├── orbit-sales/   ◄──sync──►  orbit-sales branch
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

Secrets and local data are never committed, so a fresh clone won't run until
you add them:

| App | Create | Get the values from |
|---|---|---|
| Any web app | `.env.local` in the app's folder | A teammate. At minimum `API_URL=http://127.0.0.1:8000` |
| Backend | `.env` in `orbit-backend/` | Copy `.env.example`, then fill it in |

Then install dependencies (`npm install` for a web app; see
`orbit-backend/README.md` for the API).

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
branch. The sync script brings them together. Run it from a **full clone**, on
`main`, with nothing uncommitted:

```
git switch main
bash scripts/sync-branches.sh                 # every app
bash scripts/sync-branches.sh orbit-sales     # just one app
```

For each app, it:

1. Merges anything pushed to the app branch into that app's folder on `main`.
2. Pushes `main`.
3. Rebuilds the app branch from `main` and pushes it, so app-branch
   developers get `main`'s changes the next time they `git pull`.

Run it whenever someone pushes, or at least daily. Git Bash on Windows runs it
as-is.

### If the sync stops with a conflict

This happens when the same lines were changed on `main` and on the app branch.
The script stops partway through a merge:

```
git status                 # lists the files in conflict
# fix the <<<<<<< ======= >>>>>>> markers in each file
git add .
git commit                 # finishes the merge
bash scripts/sync-branches.sh   # run it again to finish
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

1. On `main`, create the folder `orbit-<name>/`, with its own `.gitignore`
   (copy one from another app) and a `GIT-GUIDE.md`.
2. Commit and push `main`.
3. Run `bash scripts/sync-branches.sh orbit-<name>` to create its branch on
   GitHub.

---

## 8. Cheat sheet

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
| Sync main ⇄ app branches | `bash scripts/sync-branches.sh` (full clone, on `main`) |
