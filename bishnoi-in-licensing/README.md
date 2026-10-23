# Bishnoi One In-Licensing

Products being taken on from a principal.

This folder is the In-Licensing API. It has no screens yet.

| | |
|---|---|
| Screens | In the one app (`bishnoi-one-app/`): `/in-licensing` shows "Coming soon" |
| API | `backend/` · http://127.0.0.1:8306 (docs at `/docs`) |

## Run it

From the repo root:

```
npm run bishnoi-in-licensing     # this API
npm run one                      # the other APIs and the one app's screens
```

`npm run one` doesn't start this API yet; run it alone with `npm run bishnoi-in-licensing`.
There are no screens yet: `/in-licensing` in the one app shows "Coming soon".

The first run sets up `.env`, `.venv` and the packages it needs.
Settings and passwords live in `backend/.env`. They are never in Git:
ask whoever looks after the app for the values you need.

Make your first account (there is no sign-up page), in `backend/`:

```
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
```

Run the tests, in `backend/`:

```
uv run pytest
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

Deploy it by hand, the usual way: on the office Coolify server open this app and press **Redeploy**; or run `vercel --prod` in `bishnoi-in-licensing/backend`. The screens deploy once, for every module, from `bishnoi-one-app/frontend`. API only; no screens yet.

Pushing doesn't deploy; nothing goes online until you deploy it yourself (MAINTAINING.md has the steps).

## Never

- `git push --force`: it deletes other people's work.
- Commit `.env`, keys or `backend/.data/`: they're ignored on purpose.

## More

- [`backend/README.md`](backend/README.md): how this app's API works
- [The one app's README](../bishnoi-one-app/README.md): the screens for every module
- [The repo's main README](../README.md): every app, and how to set them up
- [Benchmarks](../benchmarks/README.md): what every feature is measured against
