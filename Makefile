PY := ./.venv/bin/python
export GITHUB_TOKEN ?= $(shell gh auth token 2>/dev/null)

.PHONY: install hooks validate check daily weekly render enrich clean
install:            ## create venv and install deps
	python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt
hooks:              ## install the pre-commit hook (re-renders TOOLS.md, validates yaml)
	git config core.hooksPath hooks && echo "hooks installed via core.hooksPath"
validate:           ## check registry yaml without committing
	@hooks/pre-commit || true
check:              ## validate every link, no metadata fetch
	$(PY) scripts/enrich.py --check-only && cat link_report.md
daily:              ## one day of new items
	$(PY) scripts/watch.py --days 1
weekly:             ## seven days, better signal-to-noise
	$(PY) scripts/watch.py --days 7
enrich:             ## refresh stars, downloads, citations
	$(PY) scripts/enrich.py
render:             ## regenerate TOOLS.md from registry/*.yaml
	$(PY) scripts/render.py
clean:
	rm -rf .venv registry.enriched.json link_report.md
