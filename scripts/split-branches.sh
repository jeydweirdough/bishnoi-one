#!/usr/bin/env bash
# Rebuild one branch per app from main, each holding only that app's folder at
# the top level, then push them. Run from the repo root after pushing main:
#   bash scripts/split-branches.sh            # rebuild + push every app
#   bash scripts/split-branches.sh orbit-admin # just one app
# Never commit directly on an app branch: the next run replaces it.
set -euo pipefail

remote="${REMOTE:-origin}"
cd "$(git rev-parse --show-toplevel)"

if [ "$#" -gt 0 ]; then
  apps=("$@")
else
  apps=()
  for d in orbit-*/; do apps+=("${d%/}"); done
fi

for app in "${apps[@]}"; do
  echo "==> $app"
  git subtree split -q --prefix="$app" main -b "$app-tmp"
  git branch -f "$app" "$app-tmp"
  git branch -D -q "$app-tmp"
  git push -q "$remote" "$app"
done
echo "Done."
