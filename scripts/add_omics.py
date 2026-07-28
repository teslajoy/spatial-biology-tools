#!/usr/bin/env python3
"""
one-shot: add the `omics` molecular-layer axis to every registry entry, patch
render.py to display it, and re-render TOOLS.md.

run once from anywhere inside the repo:
    python scripts/add_omics.py

safe to re-run. idempotent.

vocabulary: DNA | RNA-bulk | RNA-sc | RNA-spatial | protein-img | protein-MS |
morphology | text | multi | n/a
"""
import pathlib
import sys

import yaml

MAP = """
ai-proteomics-perspective protein-MS
mm-foundation-models-cell-bio multi
dia-nn protein-MS
dia-bert protein-MS
massnet protein-MS
idia-qc protein-MS
quantms protein-MS
deep-visual-proteomics protein-MS,morphology
spatial-proteomics-jaki protein-MS
spatial-proteomics-pdac protein-MS,protein-img
microfluidic-spatial-proteomics protein-MS
glue RNA-sc,DNA,multi
totalvi RNA-sc,protein-img,multi
geneformer RNA-sc
scfoundation RNA-sc
state RNA-sc
cellbox protein-MS,RNA-bulk
virtual-cell-challenge RNA-sc
hca-foundation-model RNA-sc,RNA-spatial
llm-agent-benchmark-singlecell RNA-sc,RNA-spatial
qust-llm RNA-spatial,morphology
pride protein-MS
massive-kb protein-MS
proteomicsml protein-MS
federated-proteomics protein-MS
trident morphology
clam morphology
mcmicro protein-img
scimap protein-img
steinbock protein-img
spatialdata n/a
ome-ngff n/a
squidpy RNA-spatial,protein-img
giotto RNA-spatial
voyager RNA-spatial
vitessce n/a
napari-spatialdata n/a
patho-bench morphology
pathbench morphology
spddb RNA-spatial
spotless RNA-spatial
paige-prostate morphology
ibex-prostate morphology
paige-pancancer morphology
spatial-clinical-gap multi
ist-qc-standards RNA-spatial
gestalt n/a
cellpose-sam morphology
stardist morphology
mesmer protein-img
instanseg protein-img,morphology
cellsam morphology
baysor RNA-spatial
rna2seg RNA-spatial,protein-img
segmentation-error-correction RNA-spatial
valis morphology,protein-img
ashlar protein-img
coda morphology,DNA
paste RNA-spatial
stalign RNA-spatial,morphology
openst RNA-spatial
soapy multi
cell2location RNA-spatial,RNA-sc
rctd RNA-spatial,RNA-sc
card RNA-spatial,RNA-sc
tangram RNA-spatial,RNA-sc
baseline-regression RNA-spatial,RNA-sc
bayesspace RNA-spatial
spagcn RNA-spatial,morphology
graphst RNA-spatial
cellcharter RNA-spatial,protein-img
banksy RNA-spatial
bass RNA-spatial
spado RNA-spatial
cellchat RNA-sc,RNA-spatial
cellphonedb RNA-sc
commot RNA-spatial
liana RNA-sc,RNA-spatial
hest morphology,RNA-spatial
istar morphology,RNA-spatial
scellst morphology,RNA-spatial
stflow morphology,RNA-spatial
triplex morphology,RNA-spatial
virchow2 morphology
virchow2g morphology
uni morphology
conch morphology,text
prov-gigapath morphology
h-optimus morphology
phikon morphology
titan morphology,text
threads morphology,multi
prism morphology,text
chief morphology
pathchat morphology,text
nicheformer RNA-sc,RNA-spatial
scgpt-spatial RNA-spatial
kronos protein-img
novae RNA-spatial
stofm RNA-spatial
heist RNA-spatial,protein-img
cellplm RNA-sc,RNA-spatial
"""


def find_root():
    for start in (pathlib.Path(__file__).resolve().parent, pathlib.Path.cwd().resolve()):
        for d in (start, *start.parents):
            if list((d / "registry").glob("*.yaml")):
                return d
    sys.exit("no registry/*.yaml found - run from inside the repo")


def assign_omics(root):
    table = {}
    for line in MAP.strip().splitlines():
        i, tags = line.split(None, 1)
        table[i] = tags.split(",")

    total = hit = 0
    counts = {}
    for f in sorted((root / "registry").glob("*.yaml")):
        entries = yaml.safe_load(open(f))
        for e in entries:
            total += 1
            tags = table.get(e["id"])
            if tags is None:
                print(f"  no mapping for '{e['id']}' - defaulting to n/a")
                tags = ["n/a"]
            else:
                hit += 1
            e["omics"] = tags
            for t in tags:
                counts[t] = counts.get(t, 0) + 1
        yaml.safe_dump(entries, open(f, "w"), sort_keys=False, width=100,
                       allow_unicode=True, default_flow_style=False)
    print(f"{hit}/{total} entries assigned an omics layer")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k:<14} {v:>3}")
    return total


def patch_render(root):
    p = root / "scripts" / "render.py"
    s = p.read_text()
    if "omics_cell" in s:
        print("render.py already patched")
        return

    s = s.replace("def datatype_cell(e):", '''OMICS_LABEL = {
    "DNA": "DNA", "RNA-bulk": "RNA (bulk)", "RNA-sc": "scRNA",
    "RNA-spatial": "spatial RNA", "protein-img": "protein (imaging)",
    "protein-MS": "protein (MS)", "morphology": "morphology",
    "text": "text", "multi": "multi-omic", "n/a": "-",
}


def omics_cell(e):
    v = e.get("omics") or []
    if isinstance(v, str):
        v = [v]
    return "<br>".join(f"`{OMICS_LABEL.get(x, x)}`" for x in v) or "-"


def datatype_cell(e):''', 1)

    s = s.replace(
        '"| tool | model type | modality | tissue | data types (in / out) | trained on | links | maturity | reality check | who speaks well of it |",\n                  "|---|---|---|---|---|---|---|---|---|---|"]',
        '"| tool | model type | omics layer | modality | tissue | data types (in / out) | trained on | links | maturity | reality check | who speaks well of it |",\n                  "|---|---|---|---|---|---|---|---|---|---|---|"]', 1)

    s = s.replace('''                clean(e.get("model_type")),
                clean(", ".join(e["modality"])''', '''                clean(e.get("model_type")),
                omics_cell(e),
                clean(", ".join(e["modality"])''', 1)

    s = s.replace("    seen_cats = set()", '''    omics_map = {}
    for e in entries:
        for o in (e.get("omics") or ["n/a"]):
            omics_map.setdefault(o, []).append(e["name"])
    lines += ["## index by molecular layer", "",
              "the axis `modality` cannot answer: which of these touch scRNA at all.",
              "", "| layer | n | tools |", "|---|---|---|"]
    for o in ["DNA", "RNA-bulk", "RNA-sc", "RNA-spatial", "protein-img",
              "protein-MS", "morphology", "text", "multi", "n/a"]:
        names = sorted(omics_map.get(o, []), key=str.lower)
        if not names:
            continue
        shown = ", ".join(names[:14]) + (f" *+{len(names)-14} more*" if len(names) > 14 else "")
        lines.append(f"| `{OMICS_LABEL.get(o, o)}` | {len(names)} | {shown} |")
    lines += ["", "---", ""]

    seen_cats = set()''', 1)

    p.write_text(s)
    print("render.py patched")


def main():
    root = find_root()
    print(f"repo root: {root}")
    assign_omics(root)
    patch_render(root)
    print("\nnow run:  python scripts/render.py")


if __name__ == "__main__":
    main()
