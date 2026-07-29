# FIJI plugin + Labkit setup and workflow

This covers installing/loading the FishROI plugin in FIJI, adding Labkit, and the full GUI workflow
(Steps 1–4). FIJI is required for **every** route; Labkit is required only for Route A segmentation.

## Contents
- Install & load the plugin
- Add Labkit (Route A)
- GUI panel map
- Step-by-step workflow
- Troubleshooting

---

## Install & load the plugin

1. Install FIJI (ImageJ2) from https://imagej.net/software/fiji/ .
2. Get the plugin file, **`fishROI_v1.py`**. (The filename itself doesn't affect behaviour.)
3. Drag the `.py` file onto the FIJI main window. It opens in the **Script Editor**.
4. Click **Run** (bottom-left of the Script Editor).
5. On launch the plugin asks you to **choose a work directory**. Everything is read from and written
   to this folder: `config.json` (remembers your last settings), ROI `.zip`s, heatmaps, and Julia
   input `.txt`. **Use one folder per experiment** and keep each image's files together with a
   consistent base filename.

The plugin is modular — you only use the panels you need and can come back for the rest later.

---

## Add Labkit (Route A only)

Labkit provides shallow-learning pixel classification for segmentation.

1. In FIJI: **Help → Update ImageJ… → Manage Update Sites**.
2. Tick **Labkit**, then **Apply and Close**, and restart FIJI when prompted.
3. Labkit user guide: https://imagej.net/plugins/labkit/ ·
   pixel-classification tutorial: https://imagej.github.io/plugins/labkit/pixel-classification-tutorial

You do **not** need Labkit if you're using Cellpose (Route B).

---

## GUI panel map

When the plugin window opens you'll see:

- **"I am analysing…"** — dropdown of the measurement to analyse: `Area`, `Mean`, `StdDev`, `Mode`,
  `Min`, `Max`, `Circ.`, `Feret`, `IntDen`, `%Area`, and many more. This choice drives Step 3
  heatmaps and Step 4 Julia code.
- **Step 1: Labkit segmentation** — a **channel** number field (the channel whose stain delineates
  your fibres — cytoplasmic phalloidin is recommended; the code labels this "membrane" for historical
  reasons), a button to open the current image in Labkit, and buttons to **Generate ROIs from simple
  segmentation** or **from probability output**. These "Generate ROI…" buttons also accept **external
  segmentation maps** (binary or probability) exported from other tools such as **ilastik**, not just
  Labkit's own output.
- **Step 1: Cellpose segmentation** — a "Cellpose instructions" button (shows a step summary and
  logs it) and **Convert ROI to Mask** (exports curated ROIs as label-mask PNGs into the work
  directory, e.g. for training a Cellpose model). Cellpose itself runs outside FIJI; see the cellpose
  reference.
- **Step 2 (Optional): manual ROI cleanup** — colour all ROIs random colours, bulk-remove ROIs
  inside a drawn selection, and **QuickSave** (timestamped snapshot folder).
- **Step 3: Generate ROI heatmaps** — heatmap **LUT** dropdown (Fire, viridis, etc.), **gamma**
  (0.05–5.00), Preview, Generate, **Bulk Generate**, Make Scalebar, Edit LUT.
- **Step 3: Heatmap with bins** — set a number of bins and design custom value ranges / colours,
  or reuse previous bin parameters.
- **Step 4 (Optional): Generate Julia input code** — Generate (single) and Bulk Generate. To analyse
  a sub-region, draw a rectangle on the image *first*.

---

## Step-by-step workflow

### Step 1 — Segmentation

**Route A (Labkit):**
1. Open your image in FIJI. Set the **channel** number of your fibre-delineating stain in the Step 1
   Labkit panel (cytoplasmic phalloidin recommended; see `references/background.md`).
2. Click the Labkit button. Adjust Brightness/Contrast when prompted, then Labkit opens.
3. Paint a few foreground (membrane) and background labels and train the classifier.
4. In Labkit: **Segmentation → Show Segmentation Result** (binary) **or → Probability Map** in
   ImageJ. Bring that result window to the front.
5. Back in the plugin, click **Generate ROIs from simple segmentation** (for the binary result) or
   **Generate ROIs from probability output** (for the probability map). Threshold/convert to mask as
   prompted, make sure **membranes are white** (use the Invert button if not), then set min/max size
   and circularity in **Analyze Particles** and confirm. ROIs land in the ROI Manager and are saved
   as a `.zip` in the work directory.

**Route B (Cellpose):** run `run_cellpose.py` outside FIJI (see cellpose reference), then in FIJI
open the **original image** and load the Cellpose ROI `.zip` into the ROI Manager
(*ROI Manager → More ▸ → Open*). Proceed to Step 3.

### Step 2 — Cleanup (optional)
Use random colouring to eyeball segmentation quality; draw a selection and **Remove ROI!** to bulk-
delete everything inside it; **QuickSave** to snapshot the current ROI set to a dated folder.

### Step 3 — Heatmaps
Pick a LUT and gamma, **Preview**, then **Generate Heatmap** (or **Bulk Generate** to run every
`.tif` in a folder that has a matching ROI `.zip`). Use **Heatmap with bins** to map value ranges to
discrete colours. **Make Scalebar** produces a matching colour ramp for figures. This step also
produces the per-ROI measurement table used later by Julia.

### Step 4 — Julia input (optional)
To analyse a sub-region, draw a **rectangle** on the heatmap/image first (otherwise the whole image
is used). Click **Generate Julia input code**. The plugin writes `<image> Julia input.txt` into the
work directory containing `image_dir`, `filename`, `pixel_length`, `dims`, `region_summary`, and the
`process_roi_data(...)` call. Paste that into the Julia script — see the Julia reference.

---

## Troubleshooting

- **Plugin won't run / import errors on `from ij import …`:** it must be run inside FIJI's Script
  Editor (Jython), not a system Python. Drag the file into FIJI and press Run.
- **Where do "Convert ROI to Mask" PNGs go?** They're written to the **work directory** you chose at
  launch (named `<image>_masks.png`), the same folder as your ROIs and heatmaps. If you don't see
  them, confirm which work directory you selected on startup.
- **Labkit not in the menus:** the update site wasn't applied or FIJI wasn't restarted. Redo
  *Help → Update ImageJ → Manage Update Sites → tick Labkit → Apply and Close*, then restart.
- **"Cannot find Labkit output":** bring the segmentation/probability window produced by
  *Segmentation → Show … in ImageJ* to the front before clicking the generate-ROIs button.
- **Membranes come out black after thresholding:** click the **Invert** button in the prompt so
  membranes are white before Analyze Particles.
- **No ROIs generated:** your Analyze Particles size/circularity limits are excluding everything —
  loosen the min size and circularity range.
- **ROIs won't save (rare, timing):** the plugin retries ~10× then asks you to save manually via the
  ROI Manager (*More ▸ → Save*).
- **Config seems stale:** delete `config.json` in the work directory to reset to defaults
  (`Area`, channel 1, gamma 1).
