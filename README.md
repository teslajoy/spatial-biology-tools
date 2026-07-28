# spatial-biology-tools

**new here? read [START-HERE.md](START-HERE.md) first.**

tooling to maintain a registry of computational tools for spatial biology and
associated modalities. this file covers how to run it. for the state-of-the-field
write-up see [`REPORT.md`](REPORT.md); for the registry itself see
[`TOOLS.md`](TOOLS.md).

```
registry/*.yaml     source of truth, hand-edited
scripts/enrich.py   resolve links, pull live metadata
scripts/render.py   registry/*.yaml -> TOOLS.md
scripts/watch.py    poll sources, write digest/YYYY-MM-DD.md
config.yaml         queries + triage weights
digest/             dated watcher output
state/seen.json     dedupe state
```

---

## quickstart

```bash
./setup.sh <your-github-user>
```

validates links, seeds watcher state, pushes the repo, enables the daily
workflow. see [`deploy/README.md`](deploy/README.md) for launchd and cron
alternatives.

---

## first run (manual)

```bash
pip install -r requirements.txt

export GITHUB_TOKEN=ghp_...              # any classic token, no scopes needed
python scripts/enrich.py --check-only    # validate every link
cat link_report.md                       # fix 404s in registry/*.yaml
```

**expect failures on the first check.** a portion of the `github:` slugs were
written from memory and never validated - the build machine hit GitHub's
unauthenticated 60 req/hr cap. paper URLs and HuggingFace ids came from live
search and are reliable. budget one pass to clear `link_report.md`.

then:

```bash
python scripts/enrich.py                       # full metadata
python scripts/render.py                       # regenerate TOOLS.md
python scripts/watch.py --days 30 --backfill   # seed state/seen.json
```

---

## credentials

none required. every source is an open API. tokens only raise limits.

| variable | source | without | with |
|---|---|---|---|
| `GITHUB_TOKEN` | GitHub REST | 60 req/hr, insufficient | 5000 req/hr |
| `S2_API_KEY` | Semantic Scholar | throttled | higher throughput |
| `HF_TOKEN` | HuggingFace | metadata ok, gated files blocked | full |
| `NCBI_API_KEY` | Europe PMC / eutils | 3 req/s | 10 req/s |

no journal logins needed. Europe PMC indexes PubMed plus bioRxiv, medRxiv and
arXiv and serves open-access full text. paywalled full text is a browser step via
the institutional proxy, deliberately not automated.

---

## scheduling

runs **daily**. GitHub Actions is configured and needs no infrastructure:

```yaml
# .github/workflows/daily-watch.yml
on:
  schedule:
    - cron: "0 13 * * *"      # 06:00 Pacific
```

it commits the digest, refreshes metadata, regenerates `TOOLS.md`, and opens an
issue when anything clears the score threshold. quiet days produce no issue.

local alternatives, both driven by `deploy/run_daily.sh` (venv, flock, logging,
git commit, desktop notification):

- **macOS** - `deploy/com.spatialbiology.daily.plist`. launchd runs a missed job
  when the laptop wakes; cron silently skips it.
- **linux** - `deploy/crontab.example`.

full instructions and a failure table: [`deploy/README.md`](deploy/README.md).

manual run: `make weekly`, or `gh workflow run 'daily spatial biology watch' -f days=7`.

`make` targets: `install`, `check`, `daily`, `weekly`, `enrich`, `render`.

---

## sources polled

| source | catches | auth |
|---|---|---|
| Europe PMC | published papers + preprints, boolean queries | none |
| bioRxiv / medRxiv | preprints ahead of PMC indexing | none |
| arXiv | q-bio, cs.CV, cs.LG method papers | none |
| GitHub search | new and fast-rising repos | token recommended |
| HuggingFace Hub | new models and datasets | none |
| ClinicalTrials.gov v2 | spatial assays entering trials | none |
| openFDA device | 510(k), de novo, PMA clearances | none |

openFDA is the only reliable signal for the `clinical` maturity column.

disable any source in `config.yaml`:

```yaml
disabled_sources: [github]
```

---

## tuning

all queries and weights live in `config.yaml`. the scripts rarely change.

```yaml
scoring:
  min_score: 2          # raise when the noise floor annoys you
  signal_terms:
    benchmark: 4        # independent evaluation beats another new method
    provenance: 4
    prospective: 4
    precancer: 4        # weighted toward active projects
  noise_terms:
    commentary: 4
    erratum: 5
```

---

## generated vs committed

`.gitignore` deliberately does **not** ignore the generated files. `TOOLS.md`,
`digest/*.md`, `registry.enriched.json`, `link_report.md` and especially
`state/seen.json` are all committed - the daily workflow git-adds exactly those.

`state/seen.json` is the one that breaks things if you ignore it: without it in
the repo, every CI run starts with an empty dedupe set and re-reports the entire
window as new.

`.gitattributes` marks the generated files `linguist-generated` so they collapse
in PR diffs and review stays on `registry/*.yaml`.

## automation

three layers, all installed by `setup.sh`:

| when | what | where |
|---|---|---|
| every commit touching `registry/` | validate yaml, check required fields, catch duplicate ids, re-render `TOOLS.md`, stage it | `hooks/pre-commit` |
| every push / PR | same validation, plus fail if `TOOLS.md` is stale, plus non-blocking link check | `.github/workflows/validate.yml` |
| daily 06:00 Pacific | poll sources, write digest, refresh metadata, open an issue | `.github/workflows/daily-watch.yml` |

install the hook manually if you cloned rather than ran `setup.sh`:

```bash
make hooks          # git config core.hooksPath hooks
make validate       # run the checks without committing
```

`core.hooksPath` is used instead of `.git/hooks/` so the hook is versioned and
travels with the repo. anyone who clones gets it after one `make hooks`.

the hook refuses the commit on malformed YAML, a missing `reality_check`, a
duplicate `id`, or the flow-sequence colon trap (`[CITE-seq: RNA + protein]`
silently parses as a dict) - that last one already bit once.

## adding an entry

schema and field rules: [`registry/SCHEMA.md`](registry/SCHEMA.md).

`reality_check` is mandatory. a row without a stated failure mode has been
collected, not evaluated.

after editing:

```bash
python scripts/enrich.py && python scripts/render.py
```

never hand-edit `TOOLS.md`. it is generated.

---

## troubleshooting

| symptom | cause |
|---|---|
| every GitHub check returns 403 | rate limit, not bad slugs. check `x-ratelimit-remaining`, set `GITHUB_TOKEN` |
| HuggingFace returns `gated` | expected for UNI, CONCH, TITAN, Virchow2, Prov-GigaPath. the repo exists; set `HF_TOKEN` to fetch files |
| arXiv collector slow | 3s sleep between calls, per their request. leave it |
| digest empty | normal on quiet days. lower `min_score` or widen `--days` |
| `seen.json` blocking re-test | `--backfill` ignores state |
