# Orbit

Orbit is a set of separate web apps (Admin, Nabhi CRM, Finance, Inventory, and
more) kept in one GitHub repo. This page shows you how to:

- get the code onto your computer
- keep it up to date
- share your changes
- run an app
- add a new app

Repo: **https://github.com/jeydweirdough/orbit**

Everyday Git is three commands: **clone** once, then **pull** and **push**.
The rest of this page walks through them.

---

## Contents

1. [How the repo is laid out](#1-how-the-repo-is-laid-out)
2. [Before you start (once per computer)](#2-before-you-start-once-per-computer)
3. [Clone: download the code](#3-clone-download-the-code)
4. [Pull and push: everyday work](#4-pull-and-push-everyday-work)
5. [Run an app](#5-run-an-app)
6. [Add a new app](#6-add-a-new-app)
7. [What happens after you push](#7-what-happens-after-you-push)
8. [Rules](#8-rules)
9. [Cheat sheet](#9-cheat-sheet)

---

## 1. How the repo is laid out

Each app is a complete web app in its own folder, with two parts:

- **`frontend/`**: the screens (Next.js)
- **`backend/`**: the API (Python, FastAPI)

The apps don't depend on each other. Each one has its own settings, database
and sign-in.

```
orbit/
├── orbit-admin/          screens :4300   API :8300
├── nabhi-crm/            screens :4302   API :8302
├── orbit-finance/        screens :4303   API :8303
├── orbit-inventory/      screens :4304   API :8304
├── orbit-platform/       screens :4305   API :8305
├── orbit-in-licensing/   screens :4306   API :8306   (screens not built yet)
├── orbit-pharmacy/       screens :4307   API :8307   (screens not built yet)
└── orbit-regulatory/     screens :4308   API :8308   (screens not built yet)
```

### Branches

| Branch | What's in it |
|---|---|
| `main` | **Everything**: every app, each in its own folder |
| `orbit-admin`, `nabhi-crm`, `orbit-finance`, … | **One app only**, named after it |

An app branch holds the same files as that app's folder on `main`. You can
work on either one; GitHub keeps them matched for you
([section 7](#7-what-happens-after-you-push)).

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
git clone -b nabhi-crm --single-branch https://github.com/jeydweirdough/orbit.git nabhi-crm
cd nabhi-crm
```

For another app, replace **both** `nabhi-crm`s with its branch name
(`orbit-admin`, `orbit-finance`, …). You get only that app, with `frontend/`
and `backend/` right at the top.

### Option B: Everything

Use this if you work across several apps, or to [add a new app](#6-add-a-new-app):

```
git clone https://github.com/jeydweirdough/orbit.git
cd orbit
```

You get `main`, with every app in its own folder.

### Then: create your settings files

Passwords and other secrets are never stored in Git. Each app includes
example files instead. Copy them once per app:

| Copy this… | …to this |
|---|---|
| `backend/.env.example` | `backend/.env` |
| `frontend/.env.example` | `frontend/.env.local` |

You're ready. See [Run an app](#5-run-an-app).

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
(see [section 7](#7-what-happens-after-you-push)).

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
| Nabhi CRM | http://localhost:4302 | http://127.0.0.1:8302 |
| Finance | http://localhost:4303 | http://127.0.0.1:8303 |
| Inventory | http://localhost:4304 | http://127.0.0.1:8304 |
| Platform | http://localhost:4305 | http://127.0.0.1:8305 |
| Licensing, Pharmacy, Regulatory | (not built) | 8306, 8307, 8308 |

### Your first account

Each app has **its own sign-in**, and there's no sign-up page. Create your
account from the app's `backend/` folder:

```
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
```

Later, `list`, `password`, `disable` and `enable` manage accounts.

### Good to know

- The database is set by `DATABASE_URL` in `backend/.env`. By default it's a
  local SQLite file in `backend/.data/`.
- Every API has interactive docs at `/docs`
  (e.g. http://127.0.0.1:8302/docs).
- Run an API's tests with `uv run pytest` in its `backend/` folder.

---

## 6. Add a new app

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

> Name your branch `add-app/<name>`. **Don't** start it with `orbit-`: those
> names are kept for the app branches.

### Step 2: Create the app's folder

Name the folder **`nabhi-<name>`**, using small letters, digits and dashes
only (e.g. `orbit-hr`, `orbit-field-sales`). This becomes your app's branch
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
(`orbit-hr`). From then on, anyone can clone just your app:

```
git clone -b orbit-hr --single-branch https://github.com/jeydweirdough/orbit.git orbit-hr
```

---

## 7. What happens after you push

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

## 8. Rules

1. **Pull before you start, and pull before you push.**
2. **Never force-push** (`git push --force`). It deletes other people's work.
3. **Never commit secrets.** `.env`, `.env.local`, keys and the backend's
   `.data/` folder are already ignored by Git. Don't force them in with
   `git add -f`.
4. **Don't open pull requests from an app branch into `main`.** The sync
   already does that. If GitHub shows a yellow "Compare & pull request"
   banner after you push to an app branch, ignore it. (Pull requests from an
   `add-app/…` or `feature/…` branch are fine.)
5. **Don't create branches that start with `orbit-` or `nabhi-`.** Those are the app
   branches, and the sync manages them.

---

## 9. Cheat sheet

| I want to… | Command |
|---|---|
| Clone one app | `git clone -b <app> --single-branch https://github.com/jeydweirdough/orbit.git <app>` |
| Clone everything | `git clone https://github.com/jeydweirdough/orbit.git` |
| Get the latest | `git pull` |
| See what I changed | `git status` / `git diff` |
| Save my changes | `git add .` then `git commit -m "what changed"` |
| Share them | `git pull` then `git push` |
| Push was rejected | `git pull --rebase` then `git push` |
| Undo my edits to one file | `git restore <file>` |
| See history | `git log --oneline` |
| Which branch am I on? | `git branch --show-current` |
| Who am I committing as? | `git config user.name` |
| Start a new app | `git switch -c add-app/<name>`, then [section 6](#6-add-a-new-app) |

---

*Looking after the repo (sync settings, tokens, reviewing new apps)? See
[MAINTAINING.md](MAINTAINING.md).*
