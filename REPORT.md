# spatial biology tooling: state of the field

a synthesis of what is currently true about computational tooling in spatial
biology and associated modalities, written to be read rather than queried.

the registry itself is [`TOOLS.md`](TOOLS.md) (77 entries). how to run the
tracker is [`README.md`](README.md). this document is the argument.

scope: spatial transcriptomics (sequencing- and imaging-based), spatial
proteomics, multiplexed tissue imaging, computational pathology on H&E and IHC,
3D and volumetric tissue reconstruction, MS-based proteomics and the AI-virtual-cell
line of work, and the foundation-model, benchmarking and data-standards layer
underneath all of it.

*compiled 2026-07-28. every claim below links to its source; where a claim rests
on a tool's own paper rather than independent evaluation, that is stated.*

---

## 1. there is no best foundation model, and the question is malformed

the single most repeated claim in this field is that some model is
state-of-the-art. the independent benchmark literature does not support a global
winner, and the disagreements are structured in a way that is more useful than a
ranking would be.

**on detection tasks, the models are interchangeable.** every DINO and DINOv2
trained encoder performs comparably on disease detection, and the choice should
be made on inference cost. a 22M-parameter distilled model ([Virchow2G-Mini](https://arxiv.org/abs/2408.00738)) is
competitive with 632M-1.1B models on [HEST-Benchmark](https://arxiv.org/abs/2406.16192). if you are paying for a
giant to do detection, you are paying for nothing.

**differentiation appears only on biomarker and prognostic tasks**, and there the
winner changes by organ. [Virchow2](https://arxiv.org/abs/2408.00738) leads vision-only models ([Nat Biomed Eng 2025](https://www.nature.com/articles/s41551-025-01516-3)). [CONCH](https://www.nature.com/articles/s41591-024-02856-4), a
vision-language model roughly an order of magnitude smaller, matches it overall
and leads on prognostic tasks. [Prov-GigaPath](https://www.nature.com/articles/s41586-024-07441-w) tops lung and pan-cancer ([41-task benchmark](https://pmc.ncbi.nlm.nih.gov/articles/PMC12236927/)), almost
certainly because lung is over-represented in its pretraining corpus. [UNI2 does
not uniformly beat UNI](https://www.nature.com/articles/s41467-025-58796-1).

three consequences:

1. **read pretraining composition before reading a leaderboard.** the
   Prov-GigaPath lung result is the canonical worked example. a leaderboard
   position is a statement about corpus overlap as much as about architecture.
2. **smaller can be better for spatial work specifically.** CONCH's lower
   embedding dimension behaves better under ridge regression; the giants suffer
   curse-of-dimensionality on the small-n regimes typical of spatial tasks.
3. **contamination cannot be audited for most of the top models.** Virchow2,
   H-optimus and Prov-GigaPath all have closed pretraining corpora. Phikon is
   TCGA-trained and therefore contaminated with respect to TCGA benchmarks, which
   is at least a knowable problem. "we cannot check" is a different risk from
   "we checked and it is fine", and reviewers are starting to ask.

**practical position:** run two encoders, not one, and include a cheap baseline.
if the foundation model does not beat the baseline on your cohort, that is the
result.

---

## 2. the tooling layer matters more than the model layer

the highest-leverage single adoption available is not a model. [TRIDENT](https://arxiv.org/abs/2502.06750) ([repo](https://github.com/mahmoodlab/TRIDENT)) takes a
directory of whole-slide images to embeddings in one command, wraps 22+ patch
encoders and 5 slide encoders behind a unified API, and reads OpenSlide, CuCIM,
OME-Zarr, CZI and SDPC. swapping encoders becomes a flag rather than a project.

this reframes the model choice question. once swapping is free, the correct
behaviour is to stop arguing about which encoder is best and just run three.

two caveats that are easy to miss:

- **licence.** TRIDENT, Virchow2, UNI, CONCH, TITAN and KRONOS are all
  CC-BY-NC-ND, non-commercial academic use only. this is endemic to the field and
  it blocks industry collaboration. Phikon is the notable open alternative and it
  underperforms, which is the actual trade.
- **slide-encoder choice moves numbers more than patch-encoder choice** on many
  tasks, and gets a fraction of the attention. TITAN, PRISM, CHIEF, Madeleine and
  Feather are all one flag apart.

---

## 3. segmentation is the largest source of irreproducibility

everything downstream of cell segmentation inherits its errors, and a [2026 Nature
Genetics paper](https://www.nature.com/articles/s41588-025-02393-x) is specifically about quantifying and correcting that propagation.
it is worth reading before trusting any cell-type proportion you have previously
computed from imaging-based spatial transcriptomics.

the current picture is that **purpose-built beats generalist**, consistently:

- multiplexed tissue (CODEX, MIBI, IMC, Vectra): [Mesmer](https://www.nature.com/articles/s41587-021-01094-0), because it takes nuclear
  and membrane channels and produces masks that respect real membranes. a
  generalist working from one channel structurally cannot do this.
- nuclei in histology: [StarDist](https://arxiv.org/abs/1806.03535) still wins, despite the foundation model wave,
  and fine-tunes from 20-50 annotated images.
- general microscopy: [Cellpose-SAM](https://doi.org/10.1101/2025.04.28.651001) is the strongest default and [beats SAM, SAM3
  and CellSAM in aggregate](https://www.emergentmind.com/topics/cellposesam) in the March 2026 comparison.
- transcript-to-cell assignment in imaging-based ST: this is the live frontier.
  [RNA2seg](https://link.springer.com/article/10.1186/s13059-025-03908-9) fuses RNA point clouds with all available stains, trains on 4M+ cells,
  and is strong zero-shot. [Baysor](https://www.nature.com/articles/s41587-021-01044-w) remains the reference for the segmentation-free
  approach.

**a warning about the numbers themselves.** reported segmentation accuracy
depends heavily on which evaluation set is used, how touching cells are scored,
and whether per-image diameter tuning is permitted. treat published head-to-head
percentages as directional only. this is a field where the benchmark design
carries more variance than the method.

---

## 4. deconvolution is solved enough, and the baseline is the finding

[cell2location](https://www.nature.com/articles/s41587-021-01139-4) and [RCTD](https://www.nature.com/articles/s41587-021-00830-w) win essentially every independent benchmark, with SONAR
joining them in the [2026 spDDB evaluation](https://www.biorxiv.org/content/10.64898/2026.05.11.724248v1.full) across 21 methods and 37 datasets.
[CARD and Tangram are close](https://www.nature.com/articles/s41467-023-37168-7). this is a rare case of benchmark agreement.

the more interesting result is negative: **[a plain regression model outperforms
almost half of the dedicated spatial deconvolution methods](https://elifesciences.org/articles/88431).** always run NNLS or
ridge as a baseline. if a method with a dependency tree cannot beat linear
regression on your data, it is not earning its place.

performance also varies substantially by tissue architecture, platform, dataset
scale and cell type, which means the ranking is conditional and a method that
wins on brain may not win on pancreas.

---

## 5. 3D is where the real methodological gap is

the destructive versus non-destructive split is the design decision, not the
software choice. serial sectioning with registration ([CODA](https://www.nature.com/articles/s41592-022-01650-9), [VALIS](https://www.nature.com/articles/s41467-023-40218-9), [PASTE2](https://www.nature.com/articles/s41592-022-01459-6),
[Open-ST](https://www.cell.com/cell/fulltext/S0092-8674(24)00636-6)) gives molecular depth and loses tissue integrity, with section tearing
and loss as the practical limiter. volumetric imaging of cleared tissue preserves
integrity and loses molecular depth.

three things worth knowing:

- **registration is a two-part problem** and the second part is the one people
  underestimate: applying transforms to multi-gigapixel images. VALIS handles
  both and writes ome.tiff, which is why it gets used.
- **[co-registration of large serial Visium stacks has been demonstrated](https://www.cell.com/cancer-cell/fulltext/S1535-6108(25)00543-4)** for 3D
  tumour progression and clonal dynamics. this is no longer speculative.
- **there is no accepted metric for 3D registration quality in molecular
  volumes.** incremental displacement across slices is what people report. it
  flags where registration failed but says nothing about whether the resulting
  biology is real. this is an open problem that someone will solve and get cited
  heavily for.

volumetric spatial transcriptomics generated from serial histology via flow
matching or diffusion is the highest-interest, lowest-validation area on the
board. track it, do not build on it yet.

---

## 6. virtual spatial transcriptomics: real signal, wrong expectations

predicting gene expression from H&E is the highest-leverage idea in the field
because H&E is ubiquitous and spatial assays are not. the honest number is that
best HEST-Benchmark correlations sit near 0.3 Pearson on top variable genes.

that is a real signal and nowhere near substitution. most methods predict fewer
than ~10k genes and degrade sharply across tissue types.

[HEST-1k](https://arxiv.org/abs/2406.16192) ([repo](https://github.com/mahmoodlab/HEST)) is the reference benchmark and its own authors flag that spatial data is
inherently noisy and label noise is unavoidable. [downstream papers add that it is
heterogeneous in acquisition technology](https://www.nature.com/articles/s41467-025-66691-y), resolution, species (mouse-heavy) and
therapeutic domain. **topping HEST does not imply transfer to your cohort**, and
that caveat is now the single most repeated line in the follow-on literature.

the credible near-term clinical application is not virtual transcriptomics but
virtual proteomics: H&E morphology combined with predicted spatial protein maps
[has outperformed conventional approaches for immunotherapy response prediction in
lung](https://journals.plos.org/plosmedicine/article?id=10.1371%2Fjournal.pmed.1005049).

---

## 7. the clinical column is nearly empty, and it is empty in a specific way

everything regulated is an H&E morphology classifier:

- [Paige Prostate Detect](https://www.paige.ai/diagnostic-ai), FDA de novo 2021, the first AI authorised in pathology,
  EU IVDR certified 2025
- Ibex Prostate Detect, FDA 510(k), February 2025
- Paige PanCancer Detect, breakthrough designation April 2025, first for
  multi-tissue
- PathChat DX, breakthrough designation

designation is not clearance, and every one of these is an adjunct that does not
make the diagnosis.

**no spatial transcriptomics or spatial proteomics diagnostic has FDA clearance** ([Nat Rev Bioeng 2026](https://www.nature.com/articles/s44222-026-00458-y)).
CLIA/CAP service labs exist and trials are running, but the assays remain
research-use-only in practice. the named blockers are cost at clinical scale,
reproducibility across centres, and the absence of multi-centre prospective
validation with clinically compliant SOPs.

the gap between what the field publishes and what a pathologist can order is
wider than the literature's tone suggests, and it is not narrowing quickly.

---

## 8. the standards layer has converged, and that is the actionable news

[SpatialData](https://www.nature.com/articles/s41592-024-02212-x) ([repo](https://github.com/scverse/spatialdata)) is now the convergence point: five primitives (images, labels, points,
shapes, tables), coordinate transforms tracked explicitly on disk, lazy loading of
larger-than-memory data, cloud IO, and a PyTorch Dataset class so models train
directly off the store. it builds on [OME-NGFF/OME-Zarr](https://www.nature.com/articles/s41592-021-01326-w), which has readers in
python, java and javascript.

as of the [June 2026 hackathon](https://index.biohackrxiv.org/2026/06/07/s6bph.html) it also has R/Bioconductor interoperability, 2.5D
and 3D rendering, chunked multiscale points, and a language-agnostic conformance
test suite for OME-NGFF coordinate transformations.

**if you are designing schema work, design against this.** it will be what
consortium submissions require.

the same argument is being made one modality over, and it is worth citing when
making the case internally: the July 2026 Nature Methods Perspective on [AI
proteomics](https://www.nature.com/articles/s41592-026-03085-y) closes not with a
modelling proposal but with a call for an AI-friendly ecosystem among data
producers and consumers. PRIDE has twenty years of deposits and the binding
constraint is metadata heterogeneity, not data volume. two fields, same
diagnosis, and in both cases the fix is schema work.

alongside it, adopt the QC metrics now: [standardised metrics for imaging-based ST
reproducibility](https://www.nature.com/articles/s41587-025-02556-5) (Nat Biotech 2025) and Xenium best-practice workflows (Nat
Methods 2025), with [GESTALT](https://www.nature.com/articles/s41588-024-02069-y) pushing minimum-information requirements. these
become submission requirements, not suggestions.

---

## 9. the adjacent modality nobody in imaging is watching

MS-based proteomics is running the same playbook one field over, and the two
literatures barely cite each other. the anchor here is Sun et al., [AI
proteomics: from protein identification to virtual
cells](https://www.nature.com/articles/s41592-026-03085-y) (Nature Methods
Perspective, 28 July 2026, Guo/Mann/Zhang). it lays out six areas AI is
reshaping - identification and quantification, protein-protein interactions and
complexes, spatial proteomics, perturbation proteomics, multi-omics integration,
and AI virtual cells - and three of them are directly continuous with everything
above. its Supplementary Table 1 is a curated tool table with model, model type,
task and article link, close enough to this registry's schema to ingest rather
than re-curate.

**Deep Visual Proteomics is the entry to know.** it uses deep-learning
segmentation to drive laser microdissection, then measures the excised cells by
ultrasensitive MS. that closes a loop antibody-panel spatial proteomics
structurally cannot: unbiased, discovery-scale protein measurement with
cell-level spatial attribution, no 40-marker ceiling. it has already produced a
therapy decision - spatial proteomics identified [JAK inhibition for a lethal
skin disease](https://doi.org/10.1038/s41586-024-08061-0) - which is more than
most spatial transcriptomics has done. the cost is throughput: it is
microdissection, so it does not scale to whole-slide the way CODEX does.

**the same failure modes recur, one field over.** sparse-sampling plus transfer
learning to infer unmeasured regions is exactly the virtual-ST bargain from
section 6, and inherits the same validation burden. transformer architectures
ported to spectra (DIA-BERT) follow the DINOv2-on-histology trajectory. corpora
framed as the contribution rather than the model (MassNet) mirror HEST-1k.

**and the same diagnosis.** the Perspective's closing argument is a call for an
"AI-friendly ecosystem" among data producers and consumers, which is a
data-infrastructure argument, not a modelling one. PRIDE has twenty years of
deposits and metadata heterogeneity is the binding constraint, not data volume.
that is the identical complaint section 10 makes about spatial.

worth also tracking: the [Virtual Cell
Challenge](https://doi.org/10.1016/j.cell.2025.05.045) and
[STATE](https://doi.org/10.1101/2025.06.26.661135). whether or not virtual cells
are reachable, they have done something the spatial foundation model space has
not: defined a community benchmark with held-out ground truth. spatial FMs are
still evaluated mostly by their own authors.

---

## 10. the standing gap worth claiming

**nothing in this registry emits FAIR provenance by default.**

three things determine whether a spatial analysis can be reproduced:

1. the registration transforms applied
2. the segmentation model and version used
3. the encoder checkpoint used

these are also the three things least often recorded. TRIDENT does not write them
into a manifest. MCMICRO tracks some of it. SpatialData tracks coordinate
transforms and nothing else in that list. no consortium data model captures all
three.

this is schema and infrastructure work rather than method work, it sits directly
between the tool ecosystem and consortium-scale data models, and almost nobody is
doing it. it is a contribution rather than a catch-up, which is a different
position from competing on encoders.

---

## 11. what to actually do

in priority order:

1. **adopt TRIDENT** for whole-slide processing. check the licence against any
   industry collaboration first.
2. **run two encoders plus a baseline**, never one. CONCH and Virchow2 is a
   reasonable pair, and record which organ each was evaluated on.
3. **audit your segmentation** against the Nature Genetics 2026 error-propagation
   work before trusting existing cell-type proportions.
4. **always run NNLS** alongside whatever deconvolution method you choose.
5. **design schema against SpatialData and OME-NGFF**, and adopt the ST QC
   metrics now rather than when they become mandatory.
6. **build `evals/`.** running three encoders on your own cohorts and recording
   what broke is worth more than any leaderboard, and it is the only asset here
   that no colleague can hand you.

---

## how this document stays honest

the registry is refreshed daily by `scripts/watch.py`. this report is not
auto-generated and should be rewritten by hand roughly quarterly, because a
synthesis that updates itself stops being a synthesis.

when rewriting, the test for every claim is whether the qualifier survived.
"Virchow2 is best" is not a finding. "Virchow2 leads vision-only models on
biomarker tasks, ties CONCH overall, and loses to it on prognostic tasks" is.
