# CLAUDE.md — fishROI automation & skill (standalone branch)

Context for Claude Code (and contributors). Humans: start with `README.md`. This branch holds the
headless automation + Claude skill; the interactive GUI plugin (`fishROI_v1.py`) is on `main`.

## What this is
fishROI is a FIJI2/Jython workflow for **semi-automated muscle morphometry in teleost fish**
(validated in zebrafish): segment fibre cross-sections → ROIs → area heatmaps → spatial
coefficient-of-variation (CoV) maps that quantify mosaic hyperplasia.

- Paper: https://doi.org/10.64898/2026.03.27.714781
- Models + test images (Zenodo): https://doi.org/10.5281/zenodo.19223252

## Layout
- `automation/` — headless pipeline:
  - `fishroi_run_all.py` — one command: segment → FIJI measure → heatmap → Julia CoV.
  - `fishroi_auto.py` — pure-Python pipeline (no FIJI; scikit-image measures).
  - `fishroi_measure_fiji.py`, `fishroi_heatmap_fiji.py` — headless FIJI (Jython) steps.
  - `fishroi_curate.py` — FIJI GUI cleanup tools for manual ROI curation.
  - `fetch_model.py`, `fiji_setup.py` — auto-fetch the rerio model / find-or-install Fiji.
  - `hpc/` — generic SLURM: GPU segment array → CPU analyze array.
- `skill/fishROI_v2/` — the Claude skill (router `SKILL.md` + `references/`, incl. `paper-summary.md`),
  and `skill/fishROI_v2/MuscleMosaicism_v3.jl` (Julia CoV/variance analysis, invoked by the CoV step).
- `example_outputs/` — sample figures.

## Run
`python automation/fishroi_run_all.py --image img.tif --outdir out/ --seg-channel 1 --julia-script skill/fishROI_v2/MuscleMosaicism_v3.jl`

## Conventions & gotchas
- **One work directory per image**; base filenames must match across `.tif` / ROI `.zip` / `.csv`
  (the Julia step matches by name). Don't hardcode paths — write under the output dir.
- **Default model = `rerio`** (paper: no benefit from stage-specific models); `--model auto` fetches
  + md5-verifies it to `~/.cache/fishroi`.
- **Pin `cellpose<4`** — 4.x is Cellpose-SAM, incompatible with rerio/cyto3 + the classic
  `channels=[ch,0]` API.
- **Default area-heatmap LUT** = the paper's Fig-2 scheme: FIJI `phase`, inverted, value 0 → black
  (small red, large blue), with a min/max scale bar above.
- **FIJI-identical numbers** from `fishroi_run_all.py`; the pure-Python path is ~5–10% off on
  area/circularity (CoV ~2%). **CoV window = 3× mean Feret**.
- **Headless FIJI:** `RoiManager` can't be built headless (AWT) — decode ROIs from the `.zip` with
  `RoiDecoder`; don't pass `--console`; Julia figures need `GKSwstype=100`.
- Keep the skill's `SKILL.md` `description` under 1024 chars (it's the trigger).
