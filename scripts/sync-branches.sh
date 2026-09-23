#!/usr/bin/env bash
# Keep main and the per-app branches in step, both ways. See GIT-GUIDE.md.
#
#   bash scripts/sync-branches.sh              # every app
#   bash scripts/sync-branches.sh orbit-admin  # just one
#
# For each app it:
#   1. merges anything pushed to the app's branch into main (its folder), then
#   2. rebuilds the app's branch from main and pushes it.
# main is pushed in between. Run it from main with a clean working tree.
set -euo pipefail

remote="${REMOTE:-origin}"
cd "$(git rev-parse --show-toplevel)"

if [ "$(git symbolic-ref --short HEAD)" != "main" ]; then
  echo "Switch to main first: git switch main" >&2; exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "Commit or stash your changes first." >&2; exit 1
fi

if [ "$#" -gt 0 ]; then
  apps=("$@")
else
  apps=()
  for d in orbit-*/; do apps+=("${d%/}"); done
fi

git pull --ff-only "$remote" main
git fetch -q "$remote"

# 1. App branches -> main, but only work pushed to the app branch itself.
#    An app branch this script built (step 2) is main's own history split out:
#    merging it back would bring the same changes in twice, and conflict with
#    anything main has done since. So it's merged only when it has commits the
#    split of main doesn't.
for app in "${apps[@]}"; do
  if git show-ref -q --verify "refs/remotes/$remote/$app"; then
    split="$(git subtree split -q --prefix="$app" main)"
    if git merge-base --is-ancestor "$remote/$app" "$split"; then
      echo "==> $app: nothing new on its branch"
    else
      echo "==> merging $remote/$app into main"
      git subtree merge -q --prefix="$app" "$remote/$app" \
        -m "Merge $app branch into main"
    fi
  fi
done
git push -q "$remote" main

# 2. main -> app branches
for app in "${apps[@]}"; do
  echo "==> rebuilding $app"
  git subtree split -q --prefix="$app" main -b "$app-sync" >/dev/null
  git branch -f "$app" "$app-sync"
  git branch -D -q "$app-sync"
  git push -q "$remote" "$app"
done
echo "Done: main and ${#apps[@]} app branch(es) are in sync."
