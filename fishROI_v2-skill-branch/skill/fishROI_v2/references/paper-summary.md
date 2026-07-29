# Paper summary — fishROI (Lu et al., bioRxiv 2026)

Condensed summary of the preprint, for explaining the science and design decisions behind the tool.
This complements `background.md` (method-choice guidance) with the paper's findings, evidence, and
numbers. Quote sparingly; cite the DOI.

- **Citation:** Lu Y, Pan M, Jamwal V, Locop J, Ruparelia A, Currie P. *fishROI: A specialized
  workflow for semi-automated muscle morphometry analysis in teleosts.* bioRxiv 2026.03.27.714781.
  doi: https://doi.org/10.64898/2026.03.27.714781 (posted 2026-03-30). CC-BY-NC-ND 4.0.
- **Authors/affiliations:** Monash University (ARMI; EMBL Australia), University of Melbourne, MDI
  Biological Laboratories. Corresponding: Yansong Lu & Peter Currie. Contact: KLu@stowers.org /
  yansong.lu@monash.edu.
- **Code/models:** https://github.com/yansong-lu/FishROI · Cellpose models + test images on Zenodo
  https://doi.org/10.5281/zenodo.19223252.

## The problem it solves

Quantitative skeletal-muscle morphometry (fiber size, shape, number, spatial arrangement) is
labor-intensive and, in **teleosts**, poorly served by existing tools. Mammalian-tuned tools depend
on **ECM / membrane markers** (e.g. WGA, collagen) and assume fairly uniform fiber size. In teleosts
this fails because:
- Teleosts grow largely by **mosaic hyperplasia** — continuous addition of small new fibers
  throughout the myotome — so fiber sizes span a wide range and small nascent fibers get misread as
  artifacts.
- ECM/membrane staining is **weak or inconsistent in larval/juvenile fish**; small fibers sit in
  narrow gaps between ECM structures with low signal-to-noise, defeating membrane-based segmentation.
- There was **no standardized way to visualize/quantify spatial morphometric variability** (the
  readout that reflects hyperplastic growth dynamics).

## Key findings (the evidence base)

1. **Cytoplasmic staining (phalloidin) beats ECM markers.** Phalloidin gives strong, consistent
   cytoplasmic labeling across all developmental stages and resolves small nascent fibers, whereas
   WGA declines markedly in early stages. → In the plugin, set the "channel" to your
   fiber-delineating cytoplasmic stain (the code calls it "membrane" for historical reasons).

2. **Deep learning (Cellpose) beats shallow learning (Labkit) for this task.** Tested on
   phalloidin-stained zebrafish trunk cross-sections at three stages — early larval (3–7 dpf), late
   larval (21–30 dpf), early juvenile (30–50 dpf). Labkit (even trained per-image) frequently failed
   to separate tightly packed fibers, especially early-larval; it improved in juveniles where ECM is
   clearer. The **stock Cellpose `cyto3`** model — with **no muscle-specific retraining** —
   performed markedly better: ~**80% true positives** with a **false-positive rate <20%** at late
   larval and early juvenile stages.

3. **A custom model mainly cuts false positives.** From **54 phalloidin images** across the three
   stages, initial (shallow+deep) segmentations were manually curated into a ground truth of
   **19,840 ROIs**, split **70/30** train/test, and used to train `cyto3`-based models. Custom
   models did **not** significantly raise the true-positive rate (only an upward trend) but
   **significantly reduced false positives** at all stages — i.e. better artifact rejection.

4. **One universal model is enough.** A single universal **`rerio`** model (trained on all images)
   showed **no significant difference** vs three stage-specific models (only a slight downward trend
   in false positives for stage-specific ones, hinting larger datasets might help). → Practical rule:
   **default to `rerio`**; stage-specific models aren't worth the overhead.

5. **CoV of fiber area quantifies mosaic hyperplasia.** Mosaic hyperplasia was previously judged only
   qualitatively. Because it increases local fiber-size heterogeneity, the tool computes the
   **coefficient of variation (CoV = SD/mean)** of cross-sectional area in a sliding circular window
   (**radius = 3× mean Feret diameter**) and maps it spatially. **Juvenile** zebrafish (active mosaic
   hyperplasia) show **elevated CoV in the deep myotome**; early larvae (no mosaic hyperplasia) do
   not — so CoV is a quantitative, comparable readout across stages/treatments/species.

**Validation criterion** (used for all accuracy numbers, and in the repo's accuracy-validation
script): a predicted ROI is a true positive if its **centroid is close** to a manual annotation
**and area overlap exceeds 65%**.

## The tool (FIJI2 / Jython plugin) — four stages

1. **Segmentation** — Route A: Labkit (shallow, inside FIJI); Route B: Cellpose (deep, standalone
   CLI, ROIs loaded back into FIJI). Can also import external maps (e.g. ilastik). Cellpose can't
   read FIJI `roi.zip`, so **Convert ROI to Mask** exports curated ROIs as label PNGs for training.
2. **ROI creation + optional manual cleanup** (Step-2 tools: random-colour to spot merges, bulk
   remove ROIs in a drawn region, QuickSave). Produces the ROI `.zip` + measurement `.csv`.
3. **Morphometric heatmaps** — colour ROIs by area/circularity/intensity/… with preset or custom
   LUTs and gamma, or discrete value bins. (The paper's Fig 2 area heatmaps use FIJI's `phase` LUT,
   inverted, with value 0 → black: small fibers red, large blue.)
4. **Variation heatmap (CoV)** — a Julia script (`MuscleMosaicism_v3.jl`) computes the sliding-window
   μ/σ/CoV maps and per-region statistics; the plugin generates the Julia input code.

## System requirements (from the paper)

- OS tested: macOS Sonoma 14.2.1, Windows 10/11, Ubuntu 22.04 LTS (64-bit).
- RAM: 8 GB min; up to **64 GB for very large images (5–10 GB)**. FIJI is mostly CPU-bound; Labkit
  and Cellpose can use a GPU. Cellpose needs a **CUDA (NVIDIA) GPU** — AMD not supported per the
  authors — and falls back to CPU (slower).
- Versions used: FIJI2 v1.54f, Labkit 0.3.11, Julia v1.10.0. GPU Cellpose training/inference on an
  HPC node (NVIDIA T4, 16 GB). Images read via Bio-Formats.

## How this maps to the automation package

- **Default model = `rerio`** (finding #4): `--model auto` fetches only rerio.
- **Cytoplasmic channel** is the segmentation channel (finding #1): `--seg-channel`.
- **CoV window = 3× mean Feret** (finding #5) is ported faithfully in both the Julia step and
  `fishroi_auto.py`.
- **Area heatmap default LUT** reproduces the paper's Fig-2 scheme (inverted `phase`, 0→black) with a
  min/max scale bar.
- **Curation** (Step 2) is preserved as the human-in-the-loop checkpoint between segment and analyze.
