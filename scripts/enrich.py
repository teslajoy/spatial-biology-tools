#!/usr/bin/env python3
"""
enrich the hand-curated registry with live metadata.

reads  registry/*.yaml
writes registry.enriched.json  (+ link_report.md)

no credentials required. optional env vars raise rate limits:
  GITHUB_TOKEN        60/hr  -> 5000/hr
  HF_TOKEN            only needed for gated repos
  S2_API_KEY          semantic scholar, higher throughput
  NCBI_API_KEY        europe pmc / eutils

usage:
  python scripts/enrich.py
  python scripts/enrich.py --check-only     # just validate links, no metadata
"""

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT / "registry"
UA = {"User-Agent": "spatial-biology-tools/1.0 (research tracker)"}

GH_TOKEN = os.environ.get("GITHUB_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")
S2_KEY = os.environ.get("S2_API_KEY")

SESSION = requests.Session()
SESSION.headers.update(UA)


def _get(url, headers=None, params=None, timeout=25):
    """single request with polite backoff on rate limit"""
    h = dict(SESSION.headers)
    if headers:
        h.update(headers)
    for attempt in range(3):
        try:
            r = SESSION.get(url, headers=h, params=params, timeout=timeout)
        except requests.RequestException as e:
            if attempt == 2:
                return None, f"network error: {e}"
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 403 and "rate limit" in r.text.lower():
            time.sleep(5 * (attempt + 1))
            continue
        return r, None
    return None, "retries exhausted"


# ---------------------------------------------------------------- github

def github_meta(slug):
    """slug is owner/repo"""
    headers = {"Accept": "application/vnd.github+json"}
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
    r, err = _get(f"https://api.github.com/repos/{slug}", headers=headers)
    if err:
        return {"status": "error", "detail": err}
    if r.status_code == 404:
        return {"status": "not_found"}
    if r.status_code != 200:
        return {"status": "error", "detail": f"HTTP {r.status_code}"}
    d = r.json()
    return {
        "status": "ok",
        "url": d.get("html_url"),
        "stars": d.get("stargazers_count"),
        "forks": d.get("forks_count"),
        "open_issues": d.get("open_issues_count"),
        "pushed_at": d.get("pushed_at"),
        "archived": d.get("archived"),
        "license": (d.get("license") or {}).get("spdx_id"),
        "language": d.get("language"),
        "description": d.get("description"),
        # the field that actually matters: is anyone still maintaining this
        "days_since_push": _days_since(d.get("pushed_at")),
    }


def _days_since(iso):
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).days
    except Exception:
        return None


# ---------------------------------------------------------------- huggingface

def hf_meta(repo_id, kind="model"):
    base = "https://huggingface.co/api"
    path = "models" if kind == "model" else "datasets"
    headers = {}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    r, err = _get(f"{base}/{path}/{repo_id}", headers=headers)
    if err:
        return {"status": "error", "detail": err}
    if r.status_code == 404:
        return {"status": "not_found"}
    if r.status_code in (401, 403):
        # gated repos still exist - that is signal, not failure
        return {"status": "gated", "url": f"https://huggingface.co/{repo_id}"}
    if r.status_code != 200:
        return {"status": "error", "detail": f"HTTP {r.status_code}"}
    d = r.json()
    return {
        "status": "ok",
        "url": f"https://huggingface.co/{repo_id}",
        "downloads_30d": d.get("downloads"),
        "likes": d.get("likes"),
        "gated": d.get("gated"),
        "last_modified": d.get("lastModified"),
        "pipeline_tag": d.get("pipeline_tag"),
        "tags": [t for t in (d.get("tags") or []) if not t.startswith("region:")][:15],
    }


# ---------------------------------------------------------------- literature

def europepmc_meta(query):
    """resolve a paper and pull citation count + open-access status"""
    r, err = _get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={"query": query, "format": "json", "pageSize": 1,
                "resultType": "core"},
    )
    if err or r is None or r.status_code != 200:
        return {"status": "error", "detail": err or "bad response"}
    hits = r.json().get("resultList", {}).get("result", [])
    if not hits:
        return {"status": "not_found"}
    h = hits[0]
    return {
        "status": "ok",
        "title": h.get("title"),
        "journal": (h.get("journalInfo") or {}).get("journal", {}).get("title"),
        "year": h.get("pubYear"),
        "doi": h.get("doi"),
        "pmid": h.get("pmid"),
        "pmcid": h.get("pmcid"),
        "cited_by": h.get("citedByCount"),
        "is_oa": h.get("isOpenAccess"),
        "url": f"https://europepmc.org/article/{h.get('source')}/{h.get('id')}"
        if h.get("id") else None,
    }


def s2_citations(doi_or_arxiv):
    """semantic scholar - citation count and, crucially, influential citations"""
    ident = doi_or_arxiv
    if ident.lower().startswith("arxiv:"):
        ident = f"arXiv:{ident.split(':', 1)[1]}"
    else:
        ident = f"DOI:{ident}"
    headers = {"x-api-key": S2_KEY} if S2_KEY else {}
    r, err = _get(
        f"https://api.semanticscholar.org/graph/v1/paper/{ident}",
        headers=headers,
        params={"fields": "title,year,citationCount,influentialCitationCount,venue"},
    )
    if err or r is None or r.status_code != 200:
        return {"status": "error"}
    d = r.json()
    return {
        "status": "ok",
        "citations": d.get("citationCount"),
        "influential_citations": d.get("influentialCitationCount"),
        "venue": d.get("venue"),
    }


# ---------------------------------------------------------------- driver

def load_registry():
    entries = []
    for f in sorted(REGISTRY_DIR.glob("*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh) or []
        for e in data:
            e["_source_file"] = f.name
            entries.append(e)
    return entries


def enrich(entries, check_only=False):
    report = []
    for e in entries:
        live = {}

        gh = e.get("github")
        if gh:
            live["github"] = github_meta(gh)
            if live["github"]["status"] != "ok":
                report.append((e["id"], "github", gh, live["github"]["status"]))

        hf = e.get("hf")
        if hf:
            live["hf"] = hf_meta(hf)
            if live["hf"]["status"] not in ("ok", "gated"):
                report.append((e["id"], "hf", hf, live["hf"]["status"]))

        if not check_only:
            paper = e.get("paper")
            if paper and isinstance(paper, str):
                if "arxiv.org/abs/" in paper:
                    aid = paper.rsplit("/", 1)[-1]
                    live["scholar"] = s2_citations(f"arxiv:{aid}")
                elif "doi.org/" in paper:
                    doi = paper.split("doi.org/", 1)[1]
                    live["scholar"] = s2_citations(doi)
                    live["literature"] = europepmc_meta(f'DOI:"{doi}"')
                else:
                    # fall back to title search on the tool name
                    live["literature"] = europepmc_meta(f'"{e["name"]}"')
            time.sleep(0.34)  # be a good citizen

        e["_live"] = live
        e["_checked_at"] = datetime.now(timezone.utc).isoformat()
    return entries, report


def write_link_report(report, path):
    lines = ["# link validation report",
             f"\ngenerated {datetime.now(timezone.utc).isoformat()}\n"]
    if not report:
        lines.append("all links resolved.\n")
    else:
        lines.append("| entry | field | value | status |")
        lines.append("|---|---|---|---|")
        for row in report:
            lines.append("| " + " | ".join(str(x) for x in row) + " |")
        lines.append("\nfix these in registry/*.yaml, then re-run.\n")
    path.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "registry.enriched.json"))
    args = ap.parse_args()

    entries = load_registry()
    print(f"loaded {len(entries)} entries from {REGISTRY_DIR}", file=sys.stderr)

    entries, report = enrich(entries, check_only=args.check_only)

    pathlib.Path(args.out).write_text(json.dumps(entries, indent=2, default=str))
    write_link_report(report, ROOT / "link_report.md")

    bad = len(report)
    print(f"wrote {args.out}; {bad} link problem(s) - see link_report.md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
