# Git guide — Licensing app (`orbit-in-licensing`)

How to clone, pull and push **just the Licensing app**. For the whole repo and how
the branches fit together, see `README.md` at the top of the `main` branch:
https://github.com/jeydweirdough/orbit/blob/main/README.md

Branch: **`orbit-in-licensing`**. It holds only this app, at the top level:

```
frontend/     the screens (Next.js)
backend/      the API (Python, FastAPI)
GIT-GUIDE.md  this guide
```

The app stands on its own: its own screens, its own API, its own database.
The same files live in the `orbit-in-licensing/` folder on `main`, and the two are kept
in sync.

---

## 1. First-time setup (once per computer)

Install Git from https://git-scm.com, then tell Git who you are:

```
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

On the shared office machine, use `git use-jeyd` or `git use-backend`
instead, and `git who` to check which account is active.

---

## 2. Clone

```
git clone -b orbit-in-licensing --single-branch https://github.com/jeydweirdough/orbit.git orbit-in-licensing
cd orbit-in-licensing
```

This downloads only the Licensing app, not the other apps.

Want everything instead? Run `git clone https://github.com/jeydweirdough/orbit.git`
and work in the `orbit-in-licensing/` folder on `main`. Sections 3–4 still apply, but your
pushes go to `main`.

---

## 3. Run it

**API** (`backend/`, Python). Secrets aren't in Git, so copy the example first:

```
cd backend
cp .env.example .env
uv sync
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
uv run main.py
```

Serves on **http://127.0.0.1:8306** (interactive docs at `/docs`). Its database
is set by `DATABASE_URL` in `.env`: SQLite in `backend/.data/` unless you
change it. Tests: `uv run pytest`.

The app has **its own sign-in**: accounts live in its own database and sign in
to this app only. There is no sign-up page. Make accounts with
`uv run python -m app.tools.users` (see `backend/README.md`).

**Screens** (`frontend/`): a placeholder, with no screens or `dev` script yet.
See `frontend/README.md` for what it's meant to become. Port **4306** is
reserved for it.

---

## 4. Pull and push

**Get the latest** (before you start, and before you push):

```
git pull
```

**Save and share your work:**

```
git status
git add .
git commit -m "Say what changed"
git push
```

`git push` sends your commits to the `orbit-in-licensing` branch on GitHub.

**Push rejected?** Someone pushed first. Pull their work, then push again:

```
git pull --rebase
git push
```

If Git reports a conflict, fix the `<<<<<<<` / `=======` / `>>>>>>>`
markers in the listed files, then `git add .`, `git rebase --continue`,
`git push`. To back out instead, run `git rebase --abort`.

---

## 5. What happens after you push

The repo maintainer runs `scripts/sync-branches.sh` on `main`, which:

- merges your pushes into the `orbit-in-licensing/` folder on `main`, and
- brings any changes made on `main` back to this branch.

After a sync, `git pull` gives you those changes. You don't need to do
anything else.

---

## 6. Rules

- **Never** `git push --force` to this branch. It deletes other people's work.
- **Never** commit secrets (`.env`, `.env.local`, keys) or local data
  (`backend/.data/`). They're already ignored, so don't force them in with
  `git add -f`.
- **Don't** open a pull request from this branch into `main`. The sync
  already handles that. Ignore GitHub's "Compare & pull request" banner.
