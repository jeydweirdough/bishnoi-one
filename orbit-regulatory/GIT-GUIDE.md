# Git guide — Regulatory app (`orbit-regulatory`)

How to clone, pull and push **just the Regulatory app**. For the whole repo and how
the branches fit together, see `GIT-GUIDE.md` at the top of the `main`
branch: https://github.com/jeydweirdough/orbit/blob/main/GIT-GUIDE.md

Branch: **`orbit-regulatory`**. It holds only this app's files, at the top level. The
same files live in the `orbit-regulatory/` folder on `main`, and the two are kept in
sync.

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
git clone -b orbit-regulatory --single-branch https://github.com/jeydweirdough/orbit.git orbit-regulatory
cd orbit-regulatory
```

This downloads only the Regulatory app, not the other apps.

Want everything instead? Run `git clone https://github.com/jeydweirdough/orbit.git`
and work in the `orbit-regulatory/` folder on `main`. Sections 3–4 still apply, but your
pushes go to `main`.

---

## 3. Run it

This app is a placeholder: it has no screens or `dev` script yet. See
`README.md` for what it's meant to become. Port **4308** is reserved for it.

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

`git push` sends your commits to the `orbit-regulatory` branch on GitHub.

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

- merges your pushes into the `orbit-regulatory/` folder on `main`, and
- brings any changes made on `main` back to this branch.

After a sync, `git pull` gives you those changes. You don't need to do
anything else.

---

## 6. Rules

- **Never** `git push --force` to this branch. It deletes other people's work.
- **Never** commit secrets (`.env`, `.env.local`, keys). They're already
  ignored, so don't force them in with `git add -f`.
- **Don't** open a pull request from this branch into `main`. The sync
  already handles that. Ignore GitHub's "Compare & pull request" banner.
