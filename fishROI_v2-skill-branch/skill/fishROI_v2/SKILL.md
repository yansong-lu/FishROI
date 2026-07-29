---
name: fishROI_v2
description: >
  Guides users through the FishROI pipeline for semi-automated muscle morphometry / ROI analysis in
  teleost fish (validated in zebrafish): a FIJI (ImageJ2) Jython plugin plus optional Cellpose
  (deep-learning segmentation) and Julia (coefficient-of-variation / spatial variance analysis). Use
  whenever the user mentions FishROI / fishROI, muscle morphometry, muscle fibre segmentation, mosaic
  hyperplasia, coefficient of variation (CoV) of fibre area, ROI heatmaps of area / circularity /
  intensity, "generate Julia input code", MuscleMosaicism.jl, run_cellpose.py, Labkit segmentation,
  the Cellpose cyto3 or "rerio" model, phalloidin / cytoplasmic staining of fish muscle, or says
  things like "I can't load the fishROI plugin", "Labkit isn't showing up", "cellpose won't find my
  model", "which segmentation should I use", "PyCall build failed", or "the Julia script can't find
  my CSV". Also use for setting up FIJI, Cellpose, or Julia for FishROI, how to cite it, or its
  system requirements.
---

# FishROI: fish muscle ROI + mosaicism analysis

FishROI (*"A specialized workflow for semi-automated muscle morphometry analysis in teleosts"*) is a
**four-stage pipeline that spans three tool environments**. Most user pain is at the setup
boundaries, not the analysis itself — so the job of this skill is to (1) help the user pick a
segmentation route, (2) set up *only* the tools that route needs, (3) walk the FIJI workflow, and
(4) troubleshoot the environment-specific gotchas.

Code, models & user manual: https://github.com/yansong-lu/FishROI.git ·
Paper: https://doi.org/10.64898/2026.03.27.714781 · Contact: KLu@stowers.org / yansong.lu@monash.edu

For the science behind the tool (why cytoplasmic staining, what CoV / mosaic hyperplasia means,
which model to start with), system requirements, and how to cite it, read `references/background.md`.

## The pipeline at a glance

```
                    ┌─ Route A: Labkit  (shallow ML, inside FIJI)  ┐
Step 1 Segmentation ┤                                              ├─► binary/probability mask
                    └─ Route B: Cellpose (deep ML, standalone CLI) ┘
                                        │
Step 2  Create ROIs from the mask (+ optional manual cleanup)  ──► ROI .zip + measurement .csv
                                        │
Step 3  Generate ROI heatmaps (area, circularity, intensity, …; optional custom bins)
                                        │
Step 4  (Optional) Generate Julia input code ──► spatial mean/variance/CV analysis
```

Steps 2–4 all happen inside the FIJI plugin. Step 1 is either inside FIJI (Labkit) or a separate
Python script (Cellpose) whose ROI output is then loaded back into FIJI.

## Step 0 — Pick the segmentation route first

Do this before setting anything up, because it determines which environment the user has to install.
If unsure, ask which they have or prefer:

| | **Route A — Labkit** | **Route B — Cellpose** |
|---|---|---|
| Runs where | Inside FIJI | Standalone Python (CLI) |
| Method | Shallow learning, user paints a few labels | Deep learning, pretrained model |
| Best when | Small datasets, no GPU, quick training, or drafting annotations to seed a deep model | Cytoplasmic staining, batches of images, reusable models |
| Extra setup | Labkit update site only | Python env + torch + a Cellpose model |
| GPU | Not needed | CUDA GPU (NVIDIA); falls back to CPU |
| Known limitation | Struggles to separate tightly packed fibres, esp. early-larval | — |

**What the authors recommend (from the paper):** for cytoplasmic staining (e.g. phalloidin), start
with Cellpose using the stock **`cyto3`** model — it segments zebrafish muscle well *without*
retraining. Their custom **`rerio`** model (Zenodo, trained on a `cyto3` base) improves things mainly
by cutting false positives, and one universal `rerio` model works across developmental stages. Use
Labkit for small jobs, when you have no GPU, or to quickly draft annotations you'll later curate and
feed into Cellpose training. See `references/background.md` for the staining rationale and the
evidence behind these recommendations.

Pretrained Cellpose models (incl. `rerio`) are on Zenodo: https://doi.org/10.5281/zenodo.19223252

> Note: the **"Cellpose instructions" button in the FIJI GUI opens a summary of these steps** (and
> logs them to the Log window), but Cellpose itself is *not* run from inside FIJI — it runs via the
> standalone `run_cellpose.py` script, and its ROI output is loaded back into FIJI.

## Environment setup — load only what the chosen route needs

Every route needs FIJI. Then add the route-specific environment, and Julia only if the user wants
Step 4.

- **FIJI plugin + Labkit (Route A, and required for all routes):** read `references/fiji-setup.md`
- **Cellpose standalone (Route B only):** read `references/cellpose-cli.md`
- **Julia mosaicism analysis (Step 4 only):** read `references/julia-mosaicism.md`
- **Science, method choice, requirements, citation (any "why" / interpretation question):** read
  `references/background.md`
- **Deeper paper detail (findings, evidence, numbers) to explain technical points:** read
  `references/paper-summary.md` (a condensed summary of the preprint)
- **Headless / automated / HPC batch runs (no GUI):** read `references/automation.md`

Read the reference file for whatever the user is currently setting up or stuck on — don't preload all
three. Each file has install steps, the exact commands, parameter meanings, and a troubleshooting
list specific to that environment.

## Running the FIJI workflow (Steps 1–4)

Full detail — including the GUI panel map and every button — is in `references/fiji-setup.md`. The
high-level flow once the plugin window is open:

1. **Launch:** drag `fishROI_v1.py` into FIJI and click **Run** in the Script Editor. On start it
   asks for a **work directory** — everything (config, ROIs, heatmaps, Julia input) is read from and
   written to there. Use one folder per experiment.
2. **Pick the parameter** to analyse in the "I am analysing…" dropdown (e.g. `Area`, `Circ.`,
   `Mean`, `Max`, `Min`). This drives the heatmap and Julia steps.
3. **Step 1 — segmentation:**
   - *Route A:* set the membrane **channel** number, click the Labkit button, train, then in Labkit
     use *Segmentation → Show Segmentation Result / Probability Map in ImageJ*, and back in the
     plugin generate ROIs from the simple **or** probability output.
   - *Route B:* run `run_cellpose.py` outside FIJI, then open the original image in FIJI and load the
     Cellpose ROI `.zip` into the ROI Manager.
4. **Step 2 — cleanup (optional):** random-colour ROIs, bulk-remove ROIs inside a drawn region,
   and QuickSave snapshots.
5. **Step 3 — heatmaps:** choose a LUT and gamma (0.05–5.00), Preview, then Generate (or Bulk
   Generate across a folder). Optionally colour by custom value **bins**. Add a Scalebar to match.
6. **Step 4 — Julia input (optional):** to analyse a sub-region, draw a rectangle first, then
   *Generate Julia input code*. This writes a `<image> Julia input.txt` you paste into the Julia
   script (see the Julia reference).

## Data handoff between tools (where things usually break)

Keep everything for one image in **one work directory with a consistent base filename**. The tools
find each other by matching filenames:

- Cellpose writes ROI zips named `<base>_diameter_<i>.zip`; when loading into FIJI the base name must
  still match the original image.
- The Julia script needs, side by side in the same folder and sharing the base filename: the ROI
  **`.zip`** *and* a measurements **`.csv`** containing `Area, XM, YM, Feret, FeretX, FeretY`. The
  CSV comes from FIJI's measurement/heatmap step — if it's missing, Julia errors on the CSV read.

## Troubleshooting index

Route the user to the matching reference file's troubleshooting section:

- Plugin won't load / Labkit missing from menus / "Convert ROI to Mask" output location →
  `references/fiji-setup.md`
- Cellpose can't find the model / no GPU used / no objects detected / wrong channel → `references/cellpose-cli.md`
- `Pkg.build("PyCall")` fails / `read_roi` not found / Julia can't find the `.csv` or `.zip` /
  region_summary looks wrong → `references/julia-mosaicism.md`

## Optional: ROI accuracy validation

The repo includes a separate FIJI/Jython script (`accuracy_validation/…`) that compares two ROI sets
by **centroid and area** (no IoU) — useful for checking a segmentation against a hand-curated ground
truth. Run it in FIJI the same way as the main plugin; point it at the two ROI `.zip` files.

## Batch / HPC note

Cellpose over many images is embarrassingly parallel and GPU-friendly. If the user is at Stowers and
wants to run `run_cellpose.py` across a large image set on the cluster, the `hpc-slurm-script` skill
can wrap it as an sbatch job (GPU partition). Keep FIJI/Labkit steps on the desktop.
