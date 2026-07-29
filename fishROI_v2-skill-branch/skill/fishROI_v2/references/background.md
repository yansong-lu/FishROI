# Background, method guidance, system requirements & citation

Context distilled from the FishROI preprint (Lu et al., bioRxiv 2026). Read this when the user asks
what the tool is for, which staining or segmentation method to use, what the CoV output means, what
hardware/OS is needed, or how to cite it.

## What FishROI is for

Semi-automated **muscle morphometry** (fiber size, shape, number, and spatial arrangement) in
**teleost fish**, validated in zebrafish. It fills a gap left by mammalian tools, which assume fairly
uniform fiber size and depend on extracellular-matrix (ECM) / membrane markers. Teleosts grow largely
by **mosaic hyperplasia** — continuous addition of small new fibers throughout the myotome — so they
show a wide range of fiber sizes, and mammalian-tuned algorithms tend to misclassify small nascent
fibers as artefacts.

## Staining: prefer a cytoplasmic marker

- The authors recommend a **cytoplasmic stain, especially phalloidin** — it labels fibers strongly
  and consistently across all developmental stages and resolves small nascent fibers.
- ECM / membrane markers (WGA, collagen, dystroglycan) can work in adult/juvenile tissue but weaken
  markedly in larval/young fish, where membrane-based segmentation then fails.
- **Implication for the plugin:** the "channel" field in Step 1 is whichever channel delineates your
  fibers. Cytoplasmic phalloidin is recommended; membrane/ECM signal is acceptable mainly in older
  samples. (The code calls this the "membrane" channel for historical reasons — set it to your
  fiber-delineating stain regardless of type.)

## Choosing a segmentation method (evidence from the paper)

- **Cellpose (deep learning)** — recommended for cytoplasmic staining, larger datasets, and reusable
  models. The stock **`cyto3`** model already segments zebrafish muscle well *without retraining*
  (~80% true positives, <20% false positives at late-larval and juvenile stages). Start here.
- The authors' custom **`rerio`** model (trained on a `cyto3` base) mainly **reduces false
  positives**. A single universal `rerio` model worked across developmental stages; stage-specific
  models gave no statistically significant additional benefit.
- **Labkit (shallow learning)** — trains in minutes on a laptop; best for small datasets or for
  drafting annotations that seed a deep-learning model. It struggles to separate tightly packed
  fibers, especially in early-larval tissue.
- **Validation criterion** used in the paper (also in the repo's accuracy-validation script): a
  predicted ROI is a true positive if its centroid is close to a manual annotation **and** area
  overlap exceeds **65%**.

## Mosaic hyperplasia & the CoV metric (Step 4)

- Step 4 quantifies fiber-size heterogeneity as the **coefficient of variation (CoV = SD / mean)** of
  cross-sectional area among neighboring ROIs, shown as a spatial heatmap.
- It is computed with a **sliding circular window of radius = 3× the mean Feret diameter**.
- Elevated local CoV marks **growth zones / active mosaic hyperplasia** — e.g. the deep myotome of
  juvenile zebrafish shows higher CoV than early larvae, which do not undergo mosaic hyperplasia.
  This gives a quantitative, comparable readout of a feature previously judged only qualitatively.

## Training a custom Cellpose model (why "Convert ROI to Mask" exists)

Cellpose cannot read FIJI's `roi.zip` format. The plugin's **Convert ROI to Mask** turns curated FIJI
ROIs (hand-drawn or shallow-learning-derived) into **label-mask PNGs** that Cellpose training accepts.
Workflow: curate ROIs → export masks → train a `cyto3`-based model. The paper's model used a 54-image
dataset (~19,840 curated ROIs) with a 70/30 train/test split. See the repo user manual for the exact
Cellpose training commands.

## Other segmentation inputs

Because Labkit outputs (binary masks or probability maps) are standard formats, the plugin can also
**import external segmentation maps from other tools** — e.g. **ilastik** — and convert them to ROIs
through the same "Generate ROI from…" buttons. Probability maps are useful for batch runs because you
can adjust the threshold per image after segmentation.

## System requirements (from the paper)

- **OS tested:** macOS Sonoma 14.2.1, Windows 10/11, Ubuntu 22.04 LTS (64-bit).
- **RAM:** 8 GB minimum; up to **64 GB recommended for very large images (5–10 GB)**.
- FIJI throughput is mostly **CPU-bound**; Labkit and Cellpose can use a GPU.
- **Cellpose needs a CUDA-capable GPU (NVIDIA); per the authors, AMD GPUs are not supported.** It
  falls back to CPU, which works but is slower.
- **Versions used by the authors:** FIJI2 v1.54f, Labkit 0.3.11, Julia v1.10.0. GPU Cellpose
  training/inference was run on an HPC node (NVIDIA T4, 16 GB).
- **Image formats:** FIJI2 reads many microscopy formats via the Bio-Formats plugin
  (https://imagej.net/formats/bio-formats).

## Citation & links

- **Paper:** Lu Y, Pan M, Jamwal V, Locop J, Ruparelia A, Currie P. *fishROI: A specialized workflow
  for semi-automated muscle morphometry analysis in teleosts.* bioRxiv 2026.03.27.714781.
  doi: https://doi.org/10.64898/2026.03.27.714781 (posted 2026-03-30).
- **Code, models & user manual:** https://github.com/yansong-lu/FishROI.git
- **Pretrained Cellpose models (incl. `rerio`):** Zenodo https://doi.org/10.5281/zenodo.19223252
- **Underlying tools:** Cellpose (Stringer et al., 2021, *Nature Methods*), Labkit (Arzt et al.,
  2022), ilastik (Berg et al., 2019).
- **Contact:** KLu@stowers.org / yansong.lu@monash.edu; corresponding author peter.currie@monash.edu
