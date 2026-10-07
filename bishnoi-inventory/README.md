# Bishnoi One Inventory

What you have, where it is, how much, what is moving, and what needs attention.

This is the **`bishnoi-inventory`** branch. It holds only this app, so you can work on
it without downloading the others. The same files are in the `bishnoi-inventory/`
folder on `main`, and GitHub keeps the two matched after every push.

| | |
|---|---|
| Screens | `frontend/` · http://localhost:4304 |
| API | `backend/` · http://127.0.0.1:8304 (docs at `/docs`) |
| Branch | `bishnoi-inventory` |
| Full guide | [GIT-GUIDE.md](GIT-GUIDE.md): every step, with what to do when something goes wrong |

## 1. Get the code (once)

```
git clone -b bishnoi-inventory --single-branch https://github.com/jeydweirdough/nabhi.git bishnoi-inventory
cd bishnoi-inventory
```

First time on this computer? Tell Git who you are first (section 1 of
[GIT-GUIDE.md](GIT-GUIDE.md)).

## 2. Run it

**API**:

```
cd backend
cp .env.example .env
uv sync
uv run main.py
```

Make your first account (there is no sign-up page):

```
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
```

**Screens**, in a second terminal:

```
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:4304.

Settings and passwords live in `.env` and `.env.local`. They are never in Git:
ask whoever looks after the app for the values you need.

## 3. Every day: pull, then push

Before you start, get everyone else's work:

```
git pull
```

When you're done, save and share yours:

```
git add .
git commit -m "Say what changed"
git pull --rebase
git push
```

**Push rejected?** Someone pushed first. Run `git pull --rebase`, then
`git push` again. If Git names a conflict, fix the files it lists (look for
`<<<<<<<`), then `git add .` and `git rebase --continue`, then `git push`.

## 4. After you push

Within a few minutes the **Sync branches** action copies your work into the
`bishnoi-inventory/` folder on `main`, and brings anything changed on `main` back here.
You don't do anything: the next `git pull` has it.

Working on `main` instead, with every app? Use the `bishnoi-inventory/` folder and the
same commands; your pushes reach this branch the same way. Push a change to
one place only, never to both.

## 5. Put it online

On GitHub: **Actions → Deploy Inventory → Run workflow**. After the Platform.

It checks everything is set up first, and stops with what to do next when
something isn't. Nothing goes online until someone runs it.

## 6. Never

- `git push --force`: it deletes other people's work.
- Commit `.env`, `.env.local`, keys or `backend/.data/`: they're ignored on purpose.
- Open a pull request from this branch into `main`: the sync does that. Ignore GitHub's "Compare & pull request" banner.

## More

- [GIT-GUIDE.md](GIT-GUIDE.md): the full step-by-step guide for this branch
- [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md): how this app's API and screens work
- [The repo's main README](https://github.com/jeydweirdough/nabhi/blob/main/README.md): every app, and how the branches fit together
- [Benchmarks](https://github.com/jeydweirdough/nabhi/blob/main/benchmarks/README.md): what every feature is measured against
