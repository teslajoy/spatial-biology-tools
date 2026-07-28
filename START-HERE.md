# start here

you have a complete repo. three commands.

```bash
cd spatial-biology-tools
chmod +x setup.sh deploy/run_daily.sh hooks/pre-commit
./setup.sh <your-github-username>
```

that is it. setup.sh does everything else: creates a python venv, validates every
link in the registry, seeds the watcher, creates and pushes the GitHub repo,
installs the git hook, and turns on the daily automation.

---

## what will happen on that first run

**it will stop with an error about dead links.** that is intended, not a bug.

some GitHub repo slugs in `registry/*.yaml` were written from memory and never
verified. setup.sh refuses to publish a registry containing 404s. you will see:

```
!! dead links found. open link_report.md, fix registry/*.yaml, re-run this script.
```

open `link_report.md`, it lists exactly which entries are broken. search the real
repo on GitHub, fix the `github:` line in the relevant `registry/*.yaml`, re-run
`./setup.sh`. expect 5-15 of them. one pass, maybe 20 minutes, never again.

---

## what each file is

| file | what it is |
|---|---|
| **TOOLS.md** | the registry. 102 tools, 10 columns. generated - never edit by hand |
| **REPORT.md** | the written synthesis of the field. 11 sections. edit by hand, quarterly |
| **README.md** | how to operate the tooling |
| **registry/*.yaml** | the source of truth. THIS is what you edit |
| **registry/SCHEMA.md** | what fields mean and the rules for filling them |
| scripts/watch.py | polls 7 sources daily, writes `digest/YYYY-MM-DD.md` |
| scripts/enrich.py | validates links, fetches stars/downloads/citations |
| scripts/render.py | registry/*.yaml -> TOOLS.md |
| config.yaml | search queries and triage scoring. the file you tune |
| hooks/pre-commit | validates yaml and re-renders TOOLS.md on every commit |
| .github/workflows/ | daily watcher + PR validation |
| deploy/ | launchd and cron alternatives if you would rather not use Actions |
| Makefile | shortcuts: `make daily`, `make check`, `make render` |

## the one rule

edit `registry/*.yaml`, never `TOOLS.md`. the hook regenerates the table on
every commit. if you edit the table directly your changes get overwritten.

## daily use, after setup

nothing. it runs at 06:00 Pacific and opens a GitHub issue when something lands.
read the issue, and if a tool is worth keeping, add a row to the appropriate
`registry/*.yaml` with a `reality_check` written in your own words.

`gh issue list --label watch` to see the digests.
