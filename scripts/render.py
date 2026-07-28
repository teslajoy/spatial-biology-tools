#!/usr/bin/env python3
"""
render TOOLS.md from registry/*.yaml (+ registry.enriched.json if present).

the markdown is generated, never hand-edited. edit the yaml.

usage:
  python scripts/render.py
"""

import json
import pathlib
from datetime import datetime, timezone

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "TOOLS.md"

CATEGORY_ORDER = [
    ("review", "anchor reviews - read these first"),
    ("patch-encoder", "patch-level encoders (H&E / brightfield)"),
    ("vision-language-encoder", "vision-language encoders"),
    ("slide-encoder", "slide-level encoders"),
    ("slide-encoder + vision-language", "slide-level multimodal"),
    ("patch-encoder + slide-encoder", "combined patch + slide"),
    ("LLM / multimodal assistant", "LLM assistants"),
    ("spatial-omics-FM", "spatial omics foundation models"),
    ("spatial-proteomics-FM", "spatial proteomics foundation models"),
    ("segmentation", "cell / nucleus segmentation"),
    ("transcript-assignment", "transcript-to-cell assignment"),
    ("registration", "image registration"),
    ("3d-reconstruction", "3D reconstruction"),
    ("alignment", "slice alignment"),
    ("platform + 3d", "platforms with 3D support"),
    ("deconvolution", "spot deconvolution"),
    ("domain-detection", "spatial domain detection"),
    ("niche-detection", "niche detection"),
    ("cell-cell-communication", "cell-cell communication"),
    ("virtual-st", "virtual spatial transcriptomics (molecules from morphology)"),
    ("benchmark + dataset", "benchmark datasets"),
    ("benchmark-harness", "benchmark harnesses"),
    ("pipeline", "processing pipelines"),
    ("analysis-toolkit", "analysis toolkits"),
    ("data-framework", "data frameworks"),
    ("standard", "standards"),
    ("visualisation", "visualisation"),
    ("consortium", "consortia"),
    ("clinical-product", "regulated / clinical products"),
    ("qc", "quality control"),
    ("ms-proteomics", "MS-based proteomics (AI)"),
    ("ms-proteomics + dataset", "MS proteomics corpora"),
    ("spatial-proteomics", "spatial proteomics by mass spectrometry"),
    ("multi-omics-integration", "multi-omics integration"),
    ("single-cell-FM", "single-cell foundation models"),
    ("perturbation-model", "perturbation / virtual cell models"),
    ("llm-tooling", "LLM tooling"),
    ("data-archive", "data archives"),
    ("method", "other methods"),
]

MATURITY = {
    "R": "research",
    "T": "translational",
    "C": "**clinical**",
    "I": "infrastructure",
}


def load():
    entries = []
    for f in sorted((ROOT / "registry").glob("*.yaml")):
        entries.extend(yaml.safe_load(open(f)) or [])
    live = {}
    p = ROOT / "registry.enriched.json"
    if p.exists():
        for e in json.loads(p.read_text()):
            live[e["id"]] = e.get("_live", {})
    return entries, live


def links(e, live):
    parts = []
    if e.get("paper"):
        parts.append(f"[paper]({e['paper']})")
    if e.get("github"):
        gh = live.get(e["id"], {}).get("github", {})
        star = f" {gh['stars']}*" if gh.get("stars") is not None else ""
        stale = ""
        if gh.get("days_since_push") is not None and gh["days_since_push"] > 365:
            stale = " :warning:stale"
        parts.append(f"[gh](https://github.com/{e['github']}){star}{stale}")
    if e.get("hf"):
        hfm = live.get(e["id"], {}).get("hf", {})
        dl = f" {hfm['downloads_30d']}dl" if hfm.get("downloads_30d") else ""
        gate = " :lock:" if hfm.get("gated") or hfm.get("status") == "gated" else ""
        parts.append(f"[hf](https://huggingface.co/{e['hf']}){dl}{gate}")
    if e.get("data"):
        d = e["data"]
        parts.append(f"[data]({d})" if str(d).startswith("http") else f"data: {d}")
    if e.get("docs"):
        parts.append(f"[docs]({e['docs']})")
    if e.get("url"):
        parts.append(f"[site]({e['url']})")
    return "<br>".join(parts) or "-"


def training_cell(e):
    t = e.get("training")
    if not t:
        return "-"
    if isinstance(t, str):
        return t
    bits = []
    if t.get("tissues"):
        bits.append(f"**tissue:** {t['tissues']}")
    if t.get("corpus"):
        bits.append(f"**corpus:** {t['corpus']}")
    if t.get("public") is not None:
        bits.append("public corpus" if t["public"] else "closed corpus")
    return "<br>".join(bits)


def datatype_cell(e):
    d = e.get("data_types")
    if not d:
        return "-"
    if isinstance(d, str):
        return d
    bits = []
    if d.get("input"):
        bits.append("**in:** " + "; ".join(d["input"]))
    if d.get("output"):
        bits.append("**out:** " + "; ".join(d["output"]))
    return "<br>".join(bits)


def endorse_cell(e):
    ends = e.get("endorsements") or []
    if not ends:
        return "-"
    out = []
    for en in ends:
        src = en.get("source", "")
        claim = en.get("claim", "")
        url = en.get("url")
        s = f"*{src}*: {claim}"
        if url:
            s = f"[{src}]({url}): {claim}"
        out.append(s)
    return "<br><br>".join(out)


def clean(s):
    if s is None:
        return "-"
    return " ".join(str(s).split()).replace("|", "/")


def main():
    entries, live = load()
    by_cat = {}
    for e in entries:
        by_cat.setdefault(e.get("category", "other"), []).append(e)

    lines = [
        "# spatial biology tool registry",
        "",
        f"generated {datetime.now(timezone.utc):%Y-%m-%d} by `scripts/render.py` "
        "- **do not edit this file**, edit `registry/*.yaml`.",
        "",
        f"{len(entries)} entries across {len(by_cat)} categories.",
        "",
        "**maturity:** `research` = papers only | `translational` = trials, atlases, "
        "biomarker discovery | `clinical` = FDA/CE-IVDR/CLAA cleared or in routine "
        "diagnostic use | `infrastructure` = substrate, not a scientific claim",
        "",
        "**tissue** = what it was trained or validated on. **data types** = what "
        "goes in and what comes out, in concrete formats.\n",
        "",
        "`:lock:` = gated download  `:warning:stale` = no push in >1 year  "
        "`*` = github stars",
        "",
        "---",
        "",
    ]

    seen_cats = set()
    ordered = [(c, label) for c, label in CATEGORY_ORDER if c in by_cat]
    ordered += [(c, c) for c in sorted(by_cat) if c not in dict(CATEGORY_ORDER)]

    for cat, label in ordered:
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        lines += [f"## {label}", "",
                  "| tool | model type | modality | tissue | data types (in / out) | trained on | links | maturity | reality check | who speaks well of it |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for e in sorted(by_cat[cat], key=lambda x: x["name"].lower()):
            lines.append("| " + " | ".join([
                f"**{e['name']}**" + (f"<br><sub>{e['org']}</sub>" if e.get("org") else ""),
                clean(e.get("model_type")),
                clean(", ".join(e["modality"]) if isinstance(e.get("modality"), list) else e.get("modality")),
                clean(e.get("tissue")),
                clean(datatype_cell(e)),
                clean(training_cell(e)),
                links(e, live),
                MATURITY.get(e.get("maturity"), "-"),
                clean(e.get("reality_check")),
                clean(endorse_cell(e)),
            ]) + " |")
        lines.append("")

    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
