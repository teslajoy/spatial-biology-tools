#!/usr/bin/env bash
# local daily runner. safe to invoke from cron or launchd.
# handles: venv, lockfile, logging, log rotation, git commit if it is a repo.
set -euo pipefail

REPO="${SPATIAL_TOOLS_DIR:-$HOME/spatial-biology-tools}"
cd "$REPO"

LOCK="$REPO/.watch.lock"
exec 9>"$LOCK"
flock -n 9 || { echo "$(date -Is) already running, skipping"; exit 0; }

LOG="$REPO/logs/watch.log"
mkdir -p "$REPO/logs"
exec >>"$LOG" 2>&1
echo "===== $(date -Is) ====="

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

# gh token if available, otherwise unauthenticated (60 req/hr, github source will be thin)
if command -v gh >/dev/null 2>&1; then
  GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"
  export GITHUB_TOKEN
fi

COUNT="$("$PY" scripts/watch.py --days "${WATCH_DAYS:-1}" | tail -1)"
echo "new items: $COUNT"

"$PY" scripts/enrich.py || echo "enrich failed, continuing"
"$PY" scripts/render.py || true

if [ -d .git ]; then
  git add digest state TOOLS.md registry.enriched.json link_report.md 2>/dev/null || true
  git diff --staged --quiet || git commit -qm "watch: $(date +%F) ($COUNT new)"
  git push -q 2>/dev/null || echo "push skipped (no remote or no auth)"
fi

# desktop notification when something landed
if [ "${COUNT:-0}" != "0" ]; then
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$COUNT new items\" with title \"spatial watch\"" || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "spatial watch" "$COUNT new items" || true
  fi
fi

# keep the log from growing forever
tail -n 5000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
