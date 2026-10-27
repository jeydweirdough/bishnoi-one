# Bishnoi One Finance

The money side of a quote.

This folder is the Finance API. Its screens are in the one app,
`bishnoi-one-app/`, with every other module's.

| | |
|---|---|
| Screens | In the one app (`bishnoi-one-app/`) · http://localhost:4301, at `/finance` |
| API | `backend/` · http://127.0.0.1:8303 (docs at `/docs`) |

## Run it

From the repo root:

```
npm run one                 # every API and the one app's screens
npm run bishnoi-finance     # this API alone
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
Settings and passwords live in `backend/.env`. They are never in Git:
ask whoever looks after the app for the values you need.

Make your first account (there is no sign-up page), in `backend/`:

```
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
```

Run the tests, in `backend/`:

```
uv run python -m pytest
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

Deploy it by hand, the usual way: on the office Coolify server open this app and press **Redeploy**; or run `vercel --prod` in `bishnoi-finance/backend`. The screens deploy once, for every module, from `bishnoi-one-app/frontend`. Any time, after the Platform.

Pushing doesn't deploy; nothing goes online until you deploy it yourself (MAINTAINING.md has the steps).

## Never

- `git push --force`: it deletes other people's work.
- Commit `.env`, keys or `backend/.data/`: they're ignored on purpose.

## More

- [`backend/README.md`](backend/README.md): how this app's API works
- [The one app's README](../bishnoi-one-app/README.md): the screens for every module
- [The repo's main README](../README.md): every app, and how to set them up
- [Benchmarks](../benchmarks/README.md): what every feature is measured against
