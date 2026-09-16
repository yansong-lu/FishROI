# Julia (Step 4): spatial mosaicism / variance analysis

`MuscleMosaicism_v3.jl` (by Michael Pan, University of Melbourne) reads the FIJI ROI output and
computes the spatial mean, standard deviation, and **coefficient of variation (CoV = SD/mean)** of
cell cross-sectional area across the tissue, plus several figures. Only needed if the user wants
Step 4.

**How to read the output:** CoV is computed in a sliding circular window of radius = **3× the mean
Feret diameter**. Elevated local CoV marks zones of high fibre-size heterogeneity — i.e. **growth
zones / active mosaic hyperplasia**. In the paper, the deep myotome of juvenile zebrafish shows
higher CoV than early larvae (which don't undergo mosaic hyperplasia), so the region statistics let
you compare hyperplasia quantitatively between samples. See `references/background.md` for the
biology.

## Contents
- Install Julia + one-time environment setup
- What the script needs on disk
- Paste the FishROI-generated input code
- Run the analysis
- Outputs
- Troubleshooting

---

## Install Julia + one-time environment setup

1. Install Julia from https://julialang.org/downloads/ (any recent stable release).
2. Start Julia. Press `]` to enter the **package manager** (prompt changes to `pkg>`), then:

   ```julia
   pkg> add DataFrames CSV Plots PyCall Conda
   ```

3. Press **Backspace** to leave the package manager (prompt back to `julia>`), then wire up the
   Python bridge that reads ImageJ ROI zips:

   ```julia
   using Conda
   Conda.add("read-roi", channel="conda-forge")
   ENV["PYTHON"] = ""          # tell PyCall to use Conda's own Python
   using Pkg
   Pkg.build("PyCall")
   ```

4. Exit: `exit()`.

This only has to be done once per machine. `ENV["PYTHON"]=""` before `Pkg.build("PyCall")` is the
important part — it makes PyCall use the Conda Python where `read-roi` was just installed.

---

## What the script needs on disk

For each image, the script reads **two files that share the same base filename, in the same folder**:

- the ROI **`.zip`** (from FIJI/Cellpose), read via the `read_roi` Python package, and
- a measurements **`.csv`** containing at least the columns
  `Area, XM, YM, Feret, FeretX, FeretY`.

The CSV is produced by FIJI's measurement/heatmap step. If it's missing or misnamed, the script
errors on the CSV read. Confirm both files exist and match before running.

---

## Paste the FishROI-generated input code

1. In FIJI, use **Step 4 → Generate Julia input code** (draw a rectangle first to restrict to a
   sub-region). This writes `<image> Julia input.txt` into the work directory, e.g.:

   ```julia
   image_dir = "/path/to/work/dir"
   filename  = "my_image"
   pixel_length = 0.1234
   dims = (512.0, 512.0)
   region_summary = ((x1,x2),(y1,y2))
   results = process_roi_data(image_dir,filename;pixel_length=pixel_length,dims=dims,region_summary=region_summary)
   ```

2. Open `MuscleMosaicism_v3.jl` in a text editor and paste that block at the **very end**, below the
   `##### Paste input code below this line #####` marker. You can stack blocks for **multiple
   samples** — one after another. Save the file.

---

## Run the analysis

```julia
julia> cd("directory_of_julia_script")
julia> include("MuscleMosaicism_v3.jl")
```

`process_roi_data` runs per sample: loads ROIs, classifies cells as mature/immature by an area
quantile cutoff, sweeps a circular window across the tissue to build mean/σ/CV maps, and (if a
`region_summary` was given) writes summary statistics for that region.

---

## Outputs

Written into `image_dir` with the sample's base filename:

- `<name>_area_hist.png` — histogram of cell areas with the maturity cutoff line
- `<name>_roi.png` — filled ROIs
- `<name>_roi_borders.png` — ROI outlines (with the analysed region boxed in red if set)
- `<name>_roi_centres.png` — ROI centroids, small cells in red
- `<name>_spatial_variance.png` — μ, σ, and σ/μ heatmaps side by side
- `<name>_area_statistics.txt` — mean, std, CV for the region (only if `region_summary` was set)

---

## Troubleshooting

- **`Pkg.build("PyCall")` fails / PyCall uses the wrong Python:** run `ENV["PYTHON"]=""` **before**
  `Pkg.build("PyCall")`, then rebuild. This forces the Conda Python. Restart Julia and retry if it
  was already loaded with a different Python.
- **`read_roi` not found / `pyimport("read_roi")` errors:** the Conda package didn't install into the
  Python PyCall uses. Re-run `using Conda; Conda.add("read-roi", channel="conda-forge")`, then
  `ENV["PYTHON"]=""; Pkg.build("PyCall")`.
- **CSV read error / no such file:** the `.csv` is missing, misnamed, or in a different folder than
  the `.zip`. They must share the base `filename` and sit in `image_dir`. Generate the measurements
  in FIJI first.
- **Missing-column error (e.g. `Area`, `XM`, `Feret`):** the CSV wasn't produced by the FishROI
  measurement step. Re-export with the plugin so the expected columns are present.
- **Coordinates look flipped (x/y swapped):** call `process_roi_data(...; transpose=true)` — the
  script has a `transpose_coords!` path for images whose axes are swapped.
- **Region box looks wrong / whole image analysed:** you didn't draw a rectangle before generating
  the input code, so `region_summary` covers everything. Redraw and regenerate, or edit the
  `region_summary` tuple by hand.
- **`Pkg` says a package is missing at `include` time:** re-enter `]` and `add DataFrames CSV Plots
  PyCall Conda`; the environment may have changed.
