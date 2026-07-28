#!/usr/bin/env python3
"""
daily discovery watcher for spatial biology tooling.

polls open APIs for anything new that looks like a tool, model, benchmark or
regulatory event in spatial biology and associated modalities, dedupes against
what has already been seen, and writes a dated markdown digest.

sources (all no-auth):
  europe pmc      papers + preprints, full boolean query support
  biorxiv/medrxiv date-range API, catches preprints before pmc indexes them
  arxiv           q-bio.QM / q-bio.GN / cs.CV / cs.LG
  github search   new repos + repos gaining stars fast
  huggingface     new models/datasets by tag and search
  clinicaltrials  v2 API, spatial assays entering trials
  openfda         device clearances (510k, de novo, PMA)

usage:
  python scripts/watch.py                    # last 1 day
  python scripts/watch.py --days 7           # weekly catch-up
  python scripts/watch.py --days 30 --backfill

state lives in state/seen.json so re-runs do not duplicate.
"""

import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
DIGEST = ROOT / "digest"
STATE.mkdir(exist_ok=True)
DIGEST.mkdir(exist_ok=True)

S = requests.Session()
S.headers.update({"User-Agent": "spatial-biology-tools-watcher/1.0 (academic research tracker)"})
GH_TOKEN = os.environ.get("GITHUB_TOKEN")


def load_config():
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def load_seen():
    p = STATE / "seen.json"
    return set(json.loads(p.read_text())) if p.exists() else set()


def save_seen(seen):
    (STATE / "seen.json").write_text(json.dumps(sorted(seen)))


def get(url, **kw):
    kw.setdefault("timeout", 30)
    try:
        r = S.get(url, **kw)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


# ------------------------------------------------------------------ sources

def europepmc(cfg, since):
    """
    europe pmc covers pubmed + agricola + preprint servers in one query.
    boolean syntax is real, so encode the scope properly rather than
    keyword-spamming.
    """
    out = []
    date_clause = f'(FIRST_PDATE:[{since} TO {datetime.now().date()}])'
    for q in cfg["queries"]["europepmc"]:
        r = get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={
                "query": f"({q}) AND {date_clause}",
                "format": "json",
                "pageSize": 50,
                "resultType": "lite",
                "sort": "P_PDATE_D desc",
            },
        )
        if not r:
            continue
        for h in r.json().get("resultList", {}).get("result", []):
            uid = f"epmc:{h.get('id')}"
            out.append({
                "uid": uid,
                "source": "europepmc",
                "title": h.get("title", "").rstrip("."),
                "authors": h.get("authorString", "")[:120],
                "venue": h.get("journalTitle") or h.get("source"),
                "date": h.get("firstPublicationDate"),
                "doi": h.get("doi"),
                "url": f"https://europepmc.org/article/{h.get('source')}/{h.get('id')}",
                "oa": h.get("isOpenAccess") == "Y",
                "matched": q[:60],
            })
        time.sleep(0.4)
    return out


def biorxiv(cfg, since):
    """
    biorxiv/medrxiv detail API returns everything in a date range, so filter
    client-side. slower but catches preprints days before pmc indexes them.
    """
    out = []
    today = datetime.now().date().isoformat()
    pat = re.compile("|".join(cfg["queries"]["keyword_filter"]), re.I)
    for server in ("biorxiv", "medrxiv"):
        cursor = 0
        while cursor < 600:  # cap the crawl
            r = get(f"https://api.biorxiv.org/details/{server}/{since}/{today}/{cursor}")
            if not r:
                break
            js = r.json()
            items = js.get("collection", [])
            if not items:
                break
            for it in items:
                blob = f"{it.get('title','')} {it.get('abstract','')}"
                if not pat.search(blob):
                    continue
                out.append({
                    "uid": f"biorxiv:{it.get('doi')}",
                    "source": server,
                    "title": it.get("title", "").rstrip("."),
                    "authors": (it.get("authors") or "")[:120],
                    "venue": server,
                    "date": it.get("date"),
                    "doi": it.get("doi"),
                    "url": f"https://doi.org/{it.get('doi')}",
                    "oa": True,
                    "matched": "keyword",
                })
            cursor += 100
            time.sleep(0.4)
    return out


def arxiv(cfg, since):
    out = []
    for q in cfg["queries"]["arxiv"]:
        url = ("http://export.arxiv.org/api/query?"
               + urllib.parse.urlencode({
                   "search_query": q,
                   "start": 0,
                   "max_results": 50,
                   "sortBy": "submittedDate",
                   "sortOrder": "descending",
               }))
        r = get(url)
        if not r:
            continue
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ElementTree.fromstring(r.text)
        for e in root.findall("a:entry", ns):
            pub = e.find("a:published", ns).text[:10]
            if pub < since:
                continue
            aid = e.find("a:id", ns).text.rsplit("/", 1)[-1]
            out.append({
                "uid": f"arxiv:{aid}",
                "source": "arxiv",
                "title": " ".join(e.find("a:title", ns).text.split()),
                "authors": ", ".join(
                    a.find("a:name", ns).text
                    for a in e.findall("a:author", ns)[:4]),
                "venue": "arXiv",
                "date": pub,
                "doi": None,
                "url": e.find("a:id", ns).text,
                "oa": True,
                "matched": q[:60],
            })
        time.sleep(3)  # arxiv asks for 3s between calls
    return out


def github_search(cfg, since):
    """new and fast-moving repos. requires a token in practice - the
    unauthenticated limit is 60/hr and search is 10/min."""
    out = []
    headers = {"Accept": "application/vnd.github+json"}
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
    for q in cfg["queries"]["github"]:
        r = get("https://api.github.com/search/repositories",
                headers=headers,
                params={"q": f"{q} created:>={since}", "sort": "stars",
                        "order": "desc", "per_page": 20})
        if not r:
            continue
        for it in r.json().get("items", []):
            out.append({
                "uid": f"gh:{it['full_name']}",
                "source": "github",
                "title": f"{it['full_name']} - {it.get('description') or ''}"[:180],
                "authors": it["owner"]["login"],
                "venue": f"{it['stargazers_count']}*",
                "date": it["created_at"][:10],
                "doi": None,
                "url": it["html_url"],
                "oa": True,
                "matched": q[:60],
            })
        time.sleep(6)
    return out


def huggingface(cfg, since):
    out = []
    for q in cfg["queries"]["huggingface"]:
        for kind in ("models", "datasets"):
            r = get(f"https://huggingface.co/api/{kind}",
                    params={"search": q, "sort": "lastModified",
                            "direction": -1, "limit": 20, "full": "true"})
            if not r:
                continue
            for it in r.json():
                lm = (it.get("lastModified") or "")[:10]
                if lm < since:
                    continue
                rid = it.get("id") or it.get("modelId")
                out.append({
                    "uid": f"hf:{kind}:{rid}",
                    "source": f"hf-{kind}",
                    "title": rid,
                    "authors": rid.split("/")[0] if "/" in rid else "",
                    "venue": f"{it.get('downloads', 0)} dl",
                    "date": lm,
                    "doi": None,
                    "url": f"https://huggingface.co/{'' if kind=='models' else 'datasets/'}{rid}",
                    "oa": not it.get("gated"),
                    "matched": q[:60],
                })
            time.sleep(0.4)
    return out


def clinicaltrials(cfg, since):
    out = []
    for q in cfg["queries"]["clinicaltrials"]:
        r = get("https://clinicaltrials.gov/api/v2/studies",
                params={"query.term": q, "pageSize": 25,
                        "sort": "LastUpdatePostDate:desc"})
        if not r:
            continue
        for st in r.json().get("studies", []):
            ident = st["protocolSection"]["identificationModule"]
            status = st["protocolSection"]["statusModule"]
            upd = (status.get("lastUpdatePostDateStruct") or {}).get("date", "")
            if upd < since:
                continue
            nct = ident["nctId"]
            out.append({
                "uid": f"ct:{nct}",
                "source": "clinicaltrials",
                "title": ident.get("briefTitle", "")[:180],
                "authors": "",
                "venue": status.get("overallStatus", ""),
                "date": upd,
                "doi": None,
                "url": f"https://clinicaltrials.gov/study/{nct}",
                "oa": True,
                "matched": q[:60],
            })
        time.sleep(0.4)
    return out


def openfda(cfg, since):
    """device clearances. the only reliable signal for the maturity=C column."""
    out = []
    since_c = since.replace("-", "")
    for endpoint, datefield in (("510k", "decision_date"),
                                ("pma", "decision_date"),
                                ("classification", None)):
        if datefield is None:
            continue
        for q in cfg["queries"]["openfda"]:
            r = get(f"https://api.fda.gov/device/{endpoint}.json",
                    params={"search": f'device_name:"{q}" AND '
                                      f'{datefield}:[{since_c} TO {datetime.now():%Y%m%d}]',
                            "limit": 20})
            if not r:
                continue
            for it in r.json().get("results", []):
                key = it.get("k_number") or it.get("pma_number") or it.get("decision_date")
                out.append({
                    "uid": f"fda:{key}",
                    "source": f"fda-{endpoint}",
                    "title": f"{it.get('device_name','')} - {it.get('applicant','')}",
                    "authors": it.get("applicant", ""),
                    "venue": it.get("decision_description", ""),
                    "date": it.get(datefield, ""),
                    "doi": None,
                    "url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm"
                           f"?ID={it.get('k_number','')}",
                    "oa": True,
                    "matched": q,
                })
            time.sleep(0.4)
    return out


# ------------------------------------------------------------------ scoring

def score(item, cfg):
    """
    crude triage so the digest leads with what is worth 60 seconds.
    tune the weights in config.yaml - this is the part you should own.
    """
    w = cfg["scoring"]
    blob = f"{item['title']} {item.get('matched','')}".lower()
    s = 0
    for term, pts in w["signal_terms"].items():
        if term in blob:
            s += pts
    for term, pts in w["noise_terms"].items():
        if term in blob:
            s -= pts
    s += w["source_bonus"].get(item["source"], 0)
    return s


# ------------------------------------------------------------------ digest

def render_digest(items, cfg, days):
    now = datetime.now(timezone.utc)
    lines = [
        f"# spatial biology watch - {now:%Y-%m-%d}",
        "",
        f"window: last {days} day(s) | {len(items)} new item(s) after dedupe",
        "",
        "scope: spatial transcriptomics, spatial proteomics, multiplexed imaging, "
        "computational pathology, 3D/volumetric tissue reconstruction, and the "
        "foundation-model + data-standards layer under all of it.",
        "",
    ]

    buckets = {}
    for it in items:
        buckets.setdefault(it["source"], []).append(it)

    hot = sorted(items, key=lambda x: -x["_score"])[:10]
    if hot:
        lines += ["## triage - highest signal", "",
                  "| score | what | source | date | link |",
                  "|---|---|---|---|---|"]
        for it in hot:
            t = it["title"].replace("|", "/")[:110]
            lines.append(f"| {it['_score']} | {t} | {it['source']} | "
                         f"{it['date']} | [link]({it['url']}) |")
        lines.append("")

    for src in sorted(buckets):
        lines += [f"## {src} ({len(buckets[src])})", ""]
        for it in sorted(buckets[src], key=lambda x: -x["_score"]):
            oa = "" if it["oa"] else " `paywalled`"
            venue = f" *{it['venue']}*" if it.get("venue") else ""
            lines.append(f"- **[{it['title'][:150]}]({it['url']})**{venue} "
                         f"- {it['date']}{oa}")
            if it.get("authors"):
                lines.append(f"  <br><sub>{it['authors']}</sub>")
        lines.append("")

    lines += [
        "---",
        "",
        "## triage protocol",
        "",
        "for anything above the score threshold, ask in order:",
        "",
        "1. is there a repo or model card, or is it a paper with no artifact? "
        "no artifact means no adoption decision, file it under watchlist.",
        "2. what tissue was it trained on, and is that your tissue?",
        "3. does it beat the plain baseline in ITS OWN paper? if the authors did "
        "not report one, that is the finding.",
        "4. licence. CC-BY-NC-ND is the norm in this field and it blocks "
        "industry collaboration.",
        "5. if it survives all four, add a row to registry/*.yaml with a "
        "`reality_check` written in your own words. a row without a stated "
        "failure mode has not been evaluated.",
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--backfill", action="store_true",
                    help="ignore seen-state, useful for a first run")
    ap.add_argument("--min-score", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config()
    since = (datetime.now() - timedelta(days=args.days)).date().isoformat()
    seen = set() if args.backfill else load_seen()

    collectors = [
        ("europepmc", europepmc),
        ("biorxiv", biorxiv),
        ("arxiv", arxiv),
        ("github", github_search),
        ("huggingface", huggingface),
        ("clinicaltrials", clinicaltrials),
        ("openfda", openfda),
    ]

    found = []
    for name, fn in collectors:
        if name in cfg.get("disabled_sources", []):
            continue
        try:
            got = fn(cfg, since)
            print(f"{name}: {len(got)}", file=sys.stderr)
            found.extend(got)
        except Exception as e:
            print(f"{name}: FAILED {e}", file=sys.stderr)

    fresh = []
    for it in found:
        if it["uid"] in seen:
            continue
        seen.add(it["uid"])
        it["_score"] = score(it, cfg)
        fresh.append(it)

    threshold = args.min_score if args.min_score is not None else cfg["scoring"]["min_score"]
    fresh = [f for f in fresh if f["_score"] >= threshold]

    out = DIGEST / f"{datetime.now():%Y-%m-%d}.md"
    out.write_text(render_digest(fresh, cfg, args.days))
    save_seen(seen)

    print(f"wrote {out} ({len(fresh)} items)", file=sys.stderr)
    # emit count for CI to decide whether to open an issue
    print(len(fresh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
