# contributing

## adding a tool

edit the right file in `registry/`:

| file | contents |
|---|---|
| `models.yaml` | foundation models - pathology encoders, spatial omics FMs |
| `methods.yaml` | analysis methods - segmentation, registration, deconvolution, CCC |
| `infra.yaml` | pipelines, data frameworks, standards, benchmarks, clinical products |
| `ai-omics.yaml` | MS proteomics, virtual cells, agents, perturbation models |

minimum viable entry:

```yaml
- id: my-tool
  name: MyTool
  category: segmentation
  model_type: U-Net variant with attention
  modality: [multiplexed IF]
  omics: [protein-img]        # DNA | RNA-bulk | RNA-sc | RNA-spatial |
                              # protein-img | protein-MS | morphology |
                              # text | multi | n/a
  tissue: breast, lung (validated on TCGA)
  data_types:
    input: [OME-TIFF, nuclear + membrane channels]
    output: [instance label mask uint16]
  paper: https://doi.org/10.xxxx/yyyy
  github: owner/repo
  license: MIT
  maturity: R
  reality_check: >
    fails on tissue with poor membrane staining. authors did not report a
    Cellpose baseline.
```

then:

```bash
make render     # regenerates TOOLS.md
git add -A && git commit -m "add MyTool"
```

the pre-commit hook validates and re-renders automatically.

## the bar for a row

**`reality_check` is mandatory and must name a failure mode.** a row without one
has been collected, not evaluated. "state of the art" is not a reality check.
"degrades on tissue outside its pretraining set; authors report no baseline" is.

**`endorsements` need qualifiers.** "beats Y" carries no information. "beats Y on
lung subtyping in TCGA but not CPTAC" does. self-citation is not an endorsement -
mark it `source: "X paper self-report"`.

**record the licence.** CC-BY-NC-ND is endemic in this field and blocks industry
collaboration. this is the field people discover too late.

**`tissue` is the field people skip and regret.** a model that never saw pancreas
will not work on pancreas.

## adding a search source

`config.yaml` holds every query and scoring weight. the scripts rarely change.
add a query, run `python scripts/watch.py --days 7 --backfill` to see what it
catches before committing.
