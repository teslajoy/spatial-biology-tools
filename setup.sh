#!/usr/bin/env bash
# one-shot bootstrap. run once, from the repo root.
#   ./setup.sh <github-user-or-org> [repo-name]
set -euo pipefail

OWNER="${1:?usage: ./setup.sh <github-user-or-org> [repo-name]}"
REPO="${2:-spatial-biology-tools}"

command -v gh >/dev/null || { echo "install gh: https://cli.github.com"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "run: gh auth login"; exit 1; }

echo "==> python env"
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

echo "==> validating links before anything is published"
GITHUB_TOKEN="$(gh auth token)" ./.venv/bin/python scripts/enrich.py --check-only
if grep -q "not_found" link_report.md; then
  echo
  echo "!! dead links found. open link_report.md, fix registry/*.yaml, re-run this script."
  echo "   (this is expected on first run - some slugs were never validated)"
  exit 1
fi

echo "==> seeding watcher state (30-day backfill, no digest spam later)"
GITHUB_TOKEN="$(gh auth token)" ./.venv/bin/python scripts/watch.py --days 30 --backfill || true

echo "==> full metadata + render"
GITHUB_TOKEN="$(gh auth token)" ./.venv/bin/python scripts/enrich.py
./.venv/bin/python scripts/render.py

echo "==> git + hooks"
[ -d .git ] || git init -q
git config core.hooksPath hooks
git add -A
git commit -qm "initial registry" || true
git branch -M main

if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  echo "    repo exists, pushing"
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
else
  gh repo create "$OWNER/$REPO" --private --source=. --remote=origin
fi
git push -u origin main

echo "==> enabling the daily workflow"
gh label create watch --color 0E8A16 --description "daily watcher digest" 2>/dev/null || true
gh workflow enable "daily spatial biology watch" 2>/dev/null || true

echo "==> optional secrets (skip with ctrl-c; both are optional)"
read -rp "Semantic Scholar API key (blank to skip): " S2 || true
[ -n "${S2:-}" ] && gh secret set S2_API_KEY --body "$S2"
read -rp "HuggingFace token, only for gated model files (blank to skip): " HFT || true
[ -n "${HFT:-}" ] && gh secret set HF_TOKEN --body "$HFT"

echo
echo "done. it now runs daily at 13:00 UTC (06:00 Pacific)."
echo "  test it now:   gh workflow run 'daily spatial biology watch' -f days=7"
echo "  watch it:      gh run watch"
echo "  digests:       gh issue list --label watch"
