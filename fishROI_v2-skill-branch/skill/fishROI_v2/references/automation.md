# Running FishROI headless / automated (no GUI, no runtime downloads)

FishROI's plugin is an interactive FIJI GUI, so it can't be driven unattended. But the pipeline can
be automated because the quality-critical step (Cellpose) is already a headless CLI and everything
downstream is deterministic. There are two levels; both use Cellpose for segmentation.

## Removing the network dependencies (works on locked-down / HPC nodes)

Don't rely on runtime downloads — **vendor the files once**:

- **`rerio` model:** download from Zenodo (https://doi.org/10.5281/zenodo.19223252) once, stage the
  file, and pass its **local path** to `run_cellpose.py` (`model = "/path/to/rerio"`). No network at
  run time — `run_cellpose.py` already loads from a path.
- **`cyto3` (stock) weights:** either pre-cache them (set `CELLPOSE_LOCAL_MODELS_PATH` to a folder
  holding the weights) or just use the local `rerio` model instead.
- **Julia `read-roi`:** it's pure Python on PyPI — `pip install read-roi` and point PyCall at that
  Python (`ENV["PYTHON"] = "/path/to/venv/bin/python"; Pkg.build("PyCall")`). This drops the
  conda-forge dependency entirely.
- **Julia itself:** vendor the release tarball, or eliminate Julia with the Python port (Option A).
- If you'd rather allowlist than vendor, an org owner can permit huggingface.co, zenodo.org,
  conda.anaconda.org, and julialang-s3.julialang.org for the environment.

## Recommended one command — `fishroi_run_all.py` (FIJI-identical, headless)

Chains **segment → FIJI-identical measure → FIJI area heatmap + LUT scale bar → Julia CoV** and
handles the glue itself (renames to `<base>.zip`/`<base>.csv` for Julia, generates + appends the
Julia input block, sets `GKSwstype=100`). Measurements come from **headless FIJI**, so absolute
area / circularity / perimeter match the published plugin (the scikit-image path in Option A is
~5–10% off on those — see the comparison at the bottom). Validated end-to-end on CPU 2026-07-29.

```bash
pip install tifffile numpy pandas scikit-image scipy matplotlib roifile opencv-python-headless
pip install "cellpose<4" torch      # MUST pin <4: cellpose 4.x = SAM, breaks rerio/cyto3

# minimal — model and FIJI are resolved automatically:
python fishroi_run_all.py --image "pSB test image.tif" --outdir out/ --seg-channel 1 \
    --julia-script ../skill/fishROI_v2/MuscleMosaicism_v3.jl     # omit to skip the CoV step
# options: --model auto (default; fetches rerio to cache) | /path/to/model
#          --fiji <launcher> (default: auto-detect, install Fiji if absent)
#          --diameter 0  --lut phase-inv-black  --pixel-um 0 (0 = read TIFF)
```

- **`--model auto`** (default) fetches the universal **rerio** model to `~/.cache/fishroi` and
  md5-verifies it (`automation/fetch_model.py`). The paper shows no benefit from the stage-specific
  DR/J/pSB models, so rerio is the only one fetched. Pass a path to use your own.
- **`--fiji`** is optional: `automation/fiji_setup.py` auto-detects a launcher (common install
  spots, cache, PATH) and **installs Fiji into the cache if none is found** (platform archive from
  downloads.imagej.net, sha256-verified).
- Segmentation uses Cellpose `io.save_rois` (the plugin's Cellpose route), so the FIJI measurements
  are truly plugin-identical. CoV additionally needs Julia with `DataFrames CSV Plots PyCall` and
  `read-roi` importable by PyCall's Python. The two FIJI steps are usable standalone:
  `fishroi_measure_fiji.py` and `fishroi_heatmap_fiji.py`.

### Two phases + a ROI checkpoint (manual curation, and GPU/CPU split)

`run_all` splits at the ROI zip so a human (or a different HPC node) can act between the halves:

```
Phase A  --segment-only   -> <base>_rois.zip     (GPU-heavy: Cellpose)
Phase B  --roizip <zip>   -> measure + heatmap + CoV   (CPU only: FIJI + Julia)
```

- **Manual ROI curation.** Cellpose is rarely perfect (the paper's Step 2 is manual cleanup). Run
  Phase A, then curate the zip in the FIJI **GUI** and re-save it, then run Phase B on the corrected
  zip — the measurements/heatmap/CoV are regenerated from *your* ROIs. Open the cleanup tools with
  `automation/fishroi_curate.py` (run WITH the GUI, i.e. **not** `--headless`):
  ```bash
  "$FIJI" --run automation/fishroi_curate.py 'image="img.tif",roizip="out/img_rois.zip"'
  ```
  It opens the image + ROIs and a "Clean up ROI tools" panel (random-colour to spot merges, draw a
  region + Remove ROI!, QuickSave straight to the zip), and **stays open** via a non-modal wait
  dialog (plain `--run` otherwise quits). Also: draw + `t` to add a fibre, select + Delete to remove
  one. Click **OK** (or QuickSave) to write back to the same zip. Launch only ONE FIJI instance at a
  time. Phase B auto-drops any zero-area / stray ROIs (`drop_degenerate_rois`) so a stray click can't
  break the run.
- **GPU/CPU:** Cellpose auto-uses CUDA when present (`--gpu auto|on|off`). Phase B is CPU-only; for
  large images pass **`--mem 48G`** (or `64%`) to size ImageJ's JVM heap.

## HPC (SLURM) batch — `automation/hpc/`

`automation/hpc/` has a generic SLURM setup that runs Phase A as a **GPU array** and Phase B as a
**CPU array** (`aftercorr` dependency, so each image's analysis starts when its segmentation
finishes — GPUs aren't held during the ImageJ/Julia work). `00_prestage.sh` stages the model + Fiji
into a shared `$FISHROI_CACHE` once (no per-task downloads/races). See `automation/hpc/README.md`.
For batch runs curation is skipped; curate interactively on a desktop for problem images only.

## Option A — headless Python pipeline (`fishroi_auto.py`)

One command does segmentation → ImageJ ROI zip → measurements → area heatmap → CoV map, **without a
FIJI install** (pure Python). Use when FIJI isn't available or you only need relative CoV; note the
measurements are scikit-image (see fidelity note). Fully batchable; ROI zips are interoperable with
FIJI/RoiManager and the Julia script.

```bash
pip install tifffile numpy pandas scikit-image scipy matplotlib roifile opencv-python-headless
pip install "cellpose<4" torch      # for the deep-learning backend (pin <4: 4.x = SAM)

python fishroi_auto.py --image sample_2.tif --outdir out/ --model auto
# --model auto fetches rerio to the cache; omit --model entirely -> watershed fallback (testing only)
```

Its area heatmap now **defaults to the same paper LUT + scale bar** as the FIJI path
(`--lut phase-inv-black`: inverted phase, small red / large blue, black background, min/max fibre
area labelled above) — reproduced in matplotlib from an embedded copy of the phase LUT, so no FIJI
is needed. Labels carry the scikit ~5% area bias (see fidelity note); use `fishroi_run_all.py` for
plugin-identical numbers.

The `--model` backend mirrors `run_cellpose.py` exactly (local model file, `channels=[ch,0]`,
`diameter=0` = auto). The CoV step is a faithful port of `MuscleMosaicism_v3.jl`
(window radius = 3× mean Feret, ≥5-fibre windows, CoV = σ/µ).

**Fidelity caveat:** measurements use scikit-image, so ImageJ-specific definitions (circularity,
Feret) are close but not bit-identical to FIJI. Use `fishroi_run_all.py` (FIJI measure) when you need
FIJI-identical numbers. Measured scikit-vs-FIJI gap on the same 124 pSB ROIs (2026-07-29): **Area
median 5.1% (scikit reads high), Circ. 7.0%, Perim. 5.9%, Feret 2.6%, centroid sub-pixel**. The
biases are systematic and one-directional, so the **CoV readout barely moves** (whole-section
0.663 scikit vs 0.677 FIJI, ~2%) — but absolute area/circularity do not match the plugin.

## Option B — headless FIJI + Julia CLI (FIJI-identical numbers)

Keep the published algorithms; just remove the interactivity.

1. **Segmentation:** Cellpose CLI (`run_cellpose.py`), as above.
2. **Area heatmap (FIJI-identical), headless — WORKING:** use
   `automation/fishroi_heatmap_fiji.py`, a Jython script run in real FIJI headless. It decodes the
   Cellpose/plugin ROI `.zip` and replicates the plugin's Step-3 mapping
   (`round(max(1, 255*(area-min)/(max-min)))` on a black 8-bit canvas) exactly, then applies a LUT.
   ```bash
   FIJI=/Applications/Fiji/Fiji.app/Contents/MacOS/fiji-macos-arm64   # adjust per platform
   "$FIJI" --headless --run automation/fishroi_heatmap_fiji.py \
       'image="img.tif",roizip="img_ROIs.zip",outdir="out"'
   ```
   **Default LUT = the paper's Figure-2 area scheme:** FIJI's `phase` LUT, **inverted**, with pixel
   value 0 → black (small fibres red, large blue, black background). Override with `lut="<name>"`
   (`"phase"` = stock, or any FIJI LUT name). **A LUT scale bar is always drawn above the heatmap** —
   a ramp in the same LUT labelled with the smallest fibre area on the red (min) end and the largest
   on the blue (max) end; pass `pixel_um="<µm/px>"` to label in µm² (else px²). Gotchas: don't pass
   `--console`; `RoiManager` can't be built headless (AWT), so ROIs are read via `RoiDecoder`
   straight from the zip.
3. **Full plugin refactor (still TODO):** to also headless-ify ROI *generation* + measurement CSV
   from a raw mask, split `fishROI_v1.py`'s processing functions from the Swing GUI and expose a
   no-dialog entry point (`ImageJ --headless --run fishROI_headless.py 'image="x.tif",channel="1",...'`).
4. **CoV:** `julia MuscleMosaicism.jl` (Julia is CLI, no GUI) with `read-roi` pip-installed so PyCall
   needs no conda. Validated end-to-end 2026-07-29 (PyCall built against a plain venv Python; run with
   `GKSwstype=100` for headless GR).

## HPC batching

See the **HPC (SLURM) batch** section above — `automation/hpc/` provides ready templates (GPU
segment array → CPU analyze array). The `hpc-slurm-script` skill can regenerate them for a different
scheduler or site conventions.
