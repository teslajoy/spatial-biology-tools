# registry entry schema

every entry is one tool. required: `id`, `name`, `category`, `maturity`, `reality_check`.

```yaml
- id: short-slug                  # unique, kebab-case, stable forever
  name: Display Name
  category: patch-encoder         # drives grouping in TOOLS.md, see scripts/render.py
  tasks: [list, of, task, tags]   # what problem it solves
  model_type: >                   # architecture AND training objective.
    "ViT-H/14 DINOv2 self-supervised" not "deep learning"
  modality: [H&E WSI, CODEX]      # assay family the tool operates on
  tissue: >                       # what it was TRAINED or VALIDATED on.
    "pancreas primary; extended to other organs" not "multi-tissue".
    a model that never saw your organ will not work on your organ.
  data_types:                     # concrete formats, not abstractions
    input: [SVS/OME-TIFF WSI tiles 224px, transcript table (x,y,gene)]
    output: [1280-d tile embedding (use CLS+mean), instance label mask uint16]
  training:
    corpus: "3.1M WSIs / 1.7B tiles"
    tissues: "pan-cancer, 31 tissue types, US real-world"
    public: false                 # can you audit the pretraining set?
  org: who built it
  paper: https://...              # doi.org or arxiv.org/abs preferred - enrich.py parses these
  github: owner/repo              # slug only, not a URL
  hf: org/model                   # huggingface repo id
  data: https://...               # associated dataset, if separable
  docs: https://...
  license: SPDX id or plain text  # CC-BY-NC-ND is endemic here - always record it
  maturity: R | T | C | I
  reality_check: >                # MANDATORY. the failure mode, in your own words.
    a row without a stated failure mode has not been evaluated, it has been
    collected. if you cannot name how it breaks, you have not used it.
  endorsements:                   # who independently speaks well of it
    - source: "Nature Biomed Eng 2025, 19 FMs / 13 cohorts"
      claim: "best vision-only model on 6-12 tasks"
      url: https://...
```

## rules

1. **self-citation does not count as an endorsement.** if the only source
   praising a model is the paper that introduced it, say so explicitly
   (`source: "X paper self-report"`).
2. **record the qualifier.** "beats Y" is not information. "beats Y on lung
   subtyping in TCGA, not on CPTAC" is.
3. **`tissue` is the field people skip and then regret.** a model that never
   saw pancreas will not work on pancreas. `training.tissues` carries the corpus
   detail; `tissue` is the short answer that renders in the table.
4. **`data_types` must be concrete.** "images" is useless. "2-channel image:
   nuclear + membrane" tells you whether your assay can feed it at all. this is
   the field that answers "can I actually chain these two tools together".
5. **licence before adoption.** CC-BY-NC-ND blocks industry collaboration and
   most of this field ships under it.
