# Cellpose (Route B): deep-learning segmentation via run_cellpose.py

Cellpose is **not** run from inside FIJI. It runs as a standalone Python script, `run_cellpose.py`,
whose ImageJ-format ROI output is then loaded back into FIJI for Steps 2–4. The in-plugin "Cellpose
instructions" button just displays a summary of the steps below.

## Contents
- Install Cellpose
- Get a pretrained model (Zenodo)
- Configure & run run_cellpose.py
- Parameter reference
- Load results into FIJI
- Troubleshooting

---

## Install Cellpose

Follow the official guide: https://github.com/mouseland/cellpose . Typical setup:

```bash
# fresh environment (conda or venv)
conda create -n cellpose python=3.10 -y
conda activate cellpose
python -m pip install cellpose

# for GPU: install a CUDA-enabled PyTorch build matching your CUDA version
# (see the cellpose GPU instructions / pytorch.org). CPU-only works too, just slower.
```

`run_cellpose.py` imports `cellpose` (`models`, `io`, `utils`), `torch`, `numpy`, `glob`. If any are
missing, `pip install` them into this environment.

---

## Get a pretrained model

**Start with the stock `cyto3` model** — the paper shows it segments zebrafish muscle well straight
out of the box (no retraining), so it's the recommended baseline for cytoplasmic staining. In
`run_cellpose.py` this is the commented alternative:

```python
# baseline: stock cyto3 (good default for cytoplasmic staining)
model = models.Cellpose(model_type="cyto3", device=device)
```

To squeeze out fewer false positives, switch to the authors' custom **`rerio`** model on Zenodo:
https://doi.org/10.5281/zenodo.19223252 — download the model file, note its **path on disk**, and use
the `models.CellposeModel(pretrained_model=model)` form already in the script. A single universal
`rerio` model works across developmental stages. If your species/tissue differs and neither fits, you
can train your own `cyto3`-based model from curated FIJI ROIs (see the "Convert ROI to Mask" note in
the FIJI reference and the training section in `references/background.md`).

---

## Configure & run

Edit the parameter block at the **top** of `run_cellpose.py`, then run it inside the cellpose env:

```python
input_folder  = "/path/to/tif/folder"     # folder of .tif images to segment
output_folder = "/path/to/roi/output"      # ROI zips are written here
channel_for_segmentation = 1               # 1 for a single-channel image; else the membrane channel
model = "/path/to/downloaded/rerio_model"  # path to the Zenodo model file
i = 0                                       # cell diameter in px; 0 = use the model's default
```

```bash
conda activate cellpose
python run_cellpose.py
```

It loads every `*.tif` in `input_folder`, runs the model, and saves ImageJ-format ROI zips named
`<image_base>_diameter_<i>.zip` into `output_folder`. Images with no detected objects are skipped
with a warning. The script prints whether it's using `cuda` or `cpu`.

---

## Parameter reference

| Variable | Meaning | Tips |
|---|---|---|
| `input_folder` | Folder scanned for `*.tif` | Change the glob in the script if your images are `.png`/`.tiff` |
| `output_folder` | Where ROI zips go | Created automatically if absent |
| `channel_for_segmentation` | Channel index for segmentation | `1` for single-channel; the membrane channel otherwise |
| `model` | Path to the pretrained model file | Loaded via `models.CellposeModel(pretrained_model=…)` |
| `i` (diameter) | Expected cell diameter in pixels | `0` lets the model estimate; set a value if fibres are consistently over/under-segmented |

---

## Load results into FIJI

1. In FIJI, open the **original image** (same base filename as the segmented `.tif`).
2. Open the ROI Manager (*Analyze → Tools → ROI Manager*), then **More ▸ → Open** and select the
   `<base>_diameter_<i>.zip`.
3. Continue with FishROI Step 2 (cleanup) / Step 3 (heatmaps) / Step 4 (Julia) as normal.

Keep the base filename consistent across the image and its ROI zip — the heatmap and Julia steps
match files by name.

---

## Troubleshooting

- **`No module named 'cellpose'` / `torch`:** you're not in the cellpose environment, or the package
  isn't installed there. `conda activate cellpose` and `pip install cellpose torch`.
- **Model won't load / file-not-found:** `model` must be the **full path** to the downloaded Zenodo
  model file, not just a name. Check the file exists and isn't a partial download.
- **Runs on CPU when you expected GPU:** the script prints the device. CPU means no CUDA-enabled
  torch/GPU was found. Cellpose needs a **CUDA-capable GPU (NVIDIA)** — per the authors, **AMD GPUs
  are not supported**. Install a CUDA torch build matching your driver, or accept slower CPU runs.
- **"No objects detected" for every image:** wrong `channel_for_segmentation`, a diameter far from
  the true cell size (try setting `i` explicitly instead of 0), or a model that doesn't match the
  tissue. Verify the channel and try the *rerio* model for zebrafish.
- **Over-/under-segmentation:** tune the diameter `i`; too small fragments cells, too large merges
  them.
- **Only some images processed:** the script only picks up `*.tif`. Convert or adjust the extension
  in the `glob.glob(...)` line.
- **Batch is slow / large image set:** run on a GPU node. At Stowers, the `hpc-slurm-script` skill
  can wrap `python run_cellpose.py` as an sbatch job on a GPU partition.
