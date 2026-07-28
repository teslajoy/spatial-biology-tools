# running it every day

three options. pick one.

## 1. GitHub Actions (recommended)

nothing to keep running, nothing to keep awake, and the digest lands as an issue
you can read on your phone. already configured in
`.github/workflows/daily-watch.yml`.

```bash
./setup.sh <your-github-user>
```

that validates links, seeds watcher state, creates and pushes the repo, enables
the workflow, and offers to set the optional secrets.

verify:

```bash
gh workflow run 'daily spatial biology watch' -f days=7   # trigger now
gh run watch                                              # follow it
gh issue list --label watch                               # read digests
```

`GITHUB_TOKEN` is injected automatically by Actions - you never set it.

## 2. launchd (macOS laptop)

better than cron on a laptop, because launchd runs a missed job when the machine
wakes rather than silently skipping it.

```bash
# edit both CHANGEME paths first
cp deploy/com.spatialbiology.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.spatialbiology.daily.plist
launchctl start com.spatialbiology.daily     # test immediately
tail -f logs/watch.log
```

## 3. cron (a machine that stays on)

```bash
crontab -e     # paste from deploy/crontab.example
```

---

## what the runner handles

`deploy/run_daily.sh` is what both local options invoke:

- uses `.venv` if present, falls back to system python
- `flock` guard, so an overrunning job never stacks
- appends to `logs/watch.log`, truncated to 5000 lines
- pulls a token from `gh auth token` when available
- commits and pushes if the directory is a git repo
- desktop notification (osascript / notify-send) only when items land

## daily vs weekly

daily is configured. quiet days produce no issue and no notification, so it costs
nothing. if the digests start feeling like noise, the fix is `min_score` in
`config.yaml` before it is the schedule - raise it to 4 and see.

## when it breaks

| symptom | check |
|---|---|
| workflow never fires | GitHub disables scheduled workflows after 60 days of repo inactivity. push anything, or `gh workflow enable` |
| empty digests every day | `min_score` too high, or `state/seen.json` already saw everything. try `--days 7` |
| github source returns nothing | no token. 60 req/hr unauthenticated is not enough for the search endpoint |
| launchd job silent | `launchctl list \| grep spatialbiology` for the exit code; `/tmp/spatialbiology.err` |
| cron job silent | cron has no PATH. set it explicitly in the crontab |
| push rejected | the Action also commits. `git pull --rebase` locally, or just use one of the two, not both |
