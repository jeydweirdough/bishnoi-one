# Bishnoi One Finance

The money side of a quote.

This folder is the Finance module of Bishnoi One's one backend (`backend/`), under
`/finance`. Its screens are in the one app, `bishnoi-one-app/`, with every other module's.

| | |
|---|---|
| Screens | In the one app (`bishnoi-one-app/`) · http://localhost:4301, at `/finance` |
| API | `backend/modules/finance` · http://127.0.0.1:8300/finance (docs at `/finance/docs`) |

## Run it

From the repo root:

```
npm run one             # the one backend (every module) and the one app's screens
npm run backend         # the backend alone
```

Open http://localhost:4301; this module is at `/finance`.

To run only Finance and its sign-in/screens, use three terminals at the repo root:

```
npm.cmd run bishnoi-platform
npm.cmd run bishnoi-finance
npm.cmd run bishnoi-one-app
```

Check for already-running services before starting another copy. The Platform
handles sign-in; the Finance command alone starts only its API.

Learning and review:
- [Offline learning guide](../docs/finance-learning-guide.html): input lifecycles,
  section interactions, examples and report sources (local 0.4.16).
- [Finance team guide](FINANCE-GUIDE.md): procedures and setup.
- [Handover](FINANCE-HANDOVER.md): architecture and dated implementation status.

The Payables screens are in the one app, including current accounts payable
aging at `/finance/bills/aging`. Its balances are current-day balances, not
reconstructed historical balances. Supplier/chart imports do not import bills,
payments or opening balances.

The first run sets up `.env`, `.venv` and the packages it needs.
Settings and passwords live in `backend/.env` (one file for every module; this module's own as
`FINANCE_<SETTING>`). They are never in Git:
ask whoever looks after the app for the values you need.

Make your first account (there is no sign-up page), in `backend/`:

```
uv run python -m modules.finance.tools.users add --email you@example.com --name "Your Name" --admin
```

Run the tests, in `backend/` (this module's only):

```
uv run python -m pytest modules/finance/tests
```

## How to work

Every app and the one app are in one repo. Clone it once and work on `main`:

```
git clone https://github.com/jeydweirdough/nabhi.git bishnoi
cd bishnoi
```

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

Want a branch for a change? Branch from `main`, but never name it `bishnoi-…`.

## Put it online

It goes online with the one backend: on the office Coolify server, **Redeploy** the backend application (every module at once), then the one app (`bishnoi-one-app/frontend`) if its screens changed.

Pushing doesn't deploy; nothing goes online until you deploy it yourself (MAINTAINING.md has the steps).

## Never

- `git push --force`: it deletes other people's work.
- Commit `.env`, keys or `backend/.data/`: they're ignored on purpose.

## More

- [API.md](API.md): how this module's API works
- [The one app's README](../../../bishnoi-one-app/README.md): the screens for every module
- [The repo's main README](../../../README.md): every app, and how to set them up
- [Benchmarks](../../../benchmarks/README.md): what every feature is measured against
